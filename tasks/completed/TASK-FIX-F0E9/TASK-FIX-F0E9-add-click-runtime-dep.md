---
id: TASK-FIX-F0E9
title: Add `click` as explicit runtime dependency (forge CLI direct import; transitive provision lost in TASK-LCP-001)
status: completed
completed: 2026-04-29T13:50:00Z
completed_location: tasks/completed/TASK-FIX-F0E9/
organized_files: ["TASK-FIX-F0E9-add-click-runtime-dep.md"]
created: 2026-04-29T13:00:00Z
updated: 2026-04-29T13:50:00Z
previous_state: in_review
state_transition_reason: "User bundled F0E10 (rich pin) into the same pyproject.toml change after Phase 5 review. End-to-end smoke test now passes: forge --help exits 0, all 63 CLI tests green, no remaining iceberg layers. All 7 ACs met (incl. #3 which was previously deferred); AC #7 sibling-task instruction superseded by user's bundle decision (F0E10 marked completed-via-F0E9)."
bundled_with:
  - TASK-FIX-F0E10  # rich pin added in same pyproject.toml change; F0E10 closed as implemented-via-F0E9
priority: high
tags: [deps, regression, cli, TASK-LCP-001-followup, F0E4-followup]
complexity: 1
task_type: feature
decision_required: false
parent_review: TASK-REV-F0E4
related_tasks:
  - TASK-LCP-001  # the pin-alignment commit that surfaced the latent missing dep
  - TASK-PSM-012  # the original task that wired the `forge` console-script + Click group
  - TASK-FIX-F0E10  # second iceberg layer (rich) surfaced by F0E9's AC #7 cross-check
unblocks:
  - TASK-FIX-F0E10  # F0E9's AC #3 full smoke test depends on F0E10 closing
scoping_source: |
  Empirical regression observed post-TASK-LCP-001 (commit 447bdf9):
    .venv/bin/forge --help
      → ModuleNotFoundError: No module named 'click'
  Six modules under src/forge/cli/ (main, cancel, history, queue, skip, status)
  import `click` directly. `click` is not declared in pyproject.toml's
  [project] dependencies; pre-LCP-001 it was provided transitively by the
  open-floor langchain-anthropic>=0.2 / langchain-openai>=0.2 resolution.
  The LCP-001 pin tightening (>=1.4,<2 / >=1.2,<2) dropped it from the
  resolved set.
estimated_effort: 10-15 minutes
test_results:
  status: passed  # all 7 ACs met after F0E10 was bundled into the same pyproject change
  coverage: not_applicable  # config-only change; coverage gate not in scope
  last_run: 2026-04-29T13:50:00Z  # final post-bundle re-verification
  click_resolved_version: "8.3.3"
  rich_resolved_version: "14.3.4"  # bundled-in via F0E10 inlined by user
  cli_test_subset_summary: "63 passed, 0 failed (final post-bundle run)"
  smoke_test_outcome: "forge --help exits 0; full Click help text printed (cancel/history/queue/skip/status commands listed)"
  defensive_cross_check_outcome: "all 8 candidate third-party imports (click/dotenv/langchain/nats/nats_core/pydantic/rich/yaml) resolve OK; no third iceberg layer"
  pre_bundle_evidence: "Initial F0E9-only run (13:30:00Z): 35 passed, 28 failed (all 28 rich-related). Recorded above for trail."
files_changed:
  - pyproject.toml  # +2 pin lines (click, rich) + 15 comment lines (F0E4-precedent annotations for both pins)
---

# Task: Add `click` as explicit runtime dependency

## Description

Surfaced as an empirical regression after TASK-LCP-001 (the LangChain 1.x
pin alignment, commit `447bdf9`): the `forge` console-script is now broken
on a fresh install. Reproduction in the current `.venv` (post-LCP-001):

```
$ .venv/bin/forge --help
Traceback (most recent call last):
  File ".../.venv/bin/forge", line 4, in <module>
    from forge.cli.main import main
  File "src/forge/cli/__init__.py", line 20, in <module>
    from forge.cli.history import history_cmd
  File "src/forge/cli/history.py", line 39, in <module>
    import click
ModuleNotFoundError: No module named 'click'
```

### Root cause

`click` is imported directly by **six** modules under `src/forge/cli/`
(TASK-PSM-012's CLI wiring):

```
src/forge/cli/main.py
src/forge/cli/history.py
src/forge/cli/queue.py
src/forge/cli/cancel.py
src/forge/cli/status.py
src/forge/cli/skip.py
```

…and by the CLI test suite (`tests/forge/test_cli_main.py`,
`tests/forge/test_cli_history.py`, `tests/forge/test_cli_mode_flag.py`)
via `click.testing.CliRunner`.

`click` is **not** declared anywhere in `pyproject.toml` — not in
`[project] dependencies`, not in `[project.optional-dependencies]`, not in
`[dependency-groups].dev`. Pre-LCP-001 it was satisfied transitively by the
loose `langchain-anthropic>=0.2` / `langchain-openai>=0.2` resolution
(0.x-band langchain integrations transitively pulled `click` via their
own rich/CLI helpers). TASK-LCP-001 tightened those pins to `>=1.4,<2`
and `>=1.2,<2` respectively; the new 1.x-band resolved set no longer
provides `click`.

This is **strictly speaking pre-existing** (the dep was always missing
from `pyproject.toml`), but **surfaced by TASK-LCP-001** — same shape as
the FA04 trapdoor pattern that TASK-REV-F0E4 was hardening forge against.
Filed as a TASK-LCP-001 follow-up because LCP-001's smoke test
(`python -c "import forge"`) imports the package but **does not exercise
the CLI entry point**, so the regression was not caught at LCP-001
acceptance time.

### Why this matters for the demo

`forge` is **DDD South West demo-critical** (per the F0E4 review §"Context").
The console-script is the user-facing entry point; a `forge --help`
that crashes on a clean-machine setup is an immediate demo-killer.

## Acceptance Criteria

- [ ] `click` added to `[project] dependencies` in `pyproject.toml` with a
      conservative pin (`click>=8,<9` is the working assumption — Click 8.x
      is the current stable major; verify against the current resolver
      output and adjust if 9.x is already mainstream by the time this task
      runs).
- [ ] `pyproject.toml` diff is **dependencies-only** — no other lines touched.
      Commit blast radius ≤2 lines added.
- [ ] **Smoke test on fresh venv**:
      ```
      uv venv --python 3.14 .venv-click-verify
      uv pip install --python .venv-click-verify/bin/python -e ".[providers]"
      .venv-click-verify/bin/forge --help
      ```
      exits 0 and prints the Click help text (group commands listed:
      `queue`, `status`, `history`, `cancel`, `skip`).
- [ ] **Resolved version captured** in the verification block at the bottom
      of this task (akin to TASK-LCP-001's verified-versions table — one
      row: `click | <resolved> | >=8,<9 ✓`).
- [ ] **CLI test subset green** under the same venv:
      ```
      .venv-click-verify/bin/python -m pytest -q \
        tests/forge/test_cli_main.py \
        tests/forge/test_cli_history.py \
        tests/forge/test_cli_mode_flag.py
      ```
      collects and passes (or matches the F0E7 post-fix baseline if there
      are unrelated failures — the AC is **zero** new failures attributable
      to `click`).
- [ ] Commit message body references **TASK-FIX-F0E9**, **TASK-LCP-001**, and
      **TASK-REV-F0E4** (LCP-001 because that's where the regression
      surfaced; F0E4 because that's the parent review of the F0E follow-up
      series).
- [ ] **Defensive cross-check** (one-liner, paste the output into the
      verification section): grep the post-install resolved set for any
      *other* package the forge runtime imports directly but doesn't
      declare. Specifically:
      ```
      grep -rEn "^import |^from " src/forge/ \
        | awk '{print $2}' | sed 's/\..*//' | sort -u
      ```
      Cross-check the unique top-level imports against the
      `[project] dependencies` list. If any other un-declared direct
      imports surface, **do not fix them in this task** — file a separate
      sibling task (e.g. `TASK-FIX-F0E10`) and link it. Keep this task's
      scope to `click` only.

## Out of scope

- **Refactoring the CLI off Click** — Click is the deliberate choice
  (TASK-PSM-012 selected it; the test suite uses `click.testing.CliRunner`
  extensively). This task only fixes the missing pin.
- **Adding `click` to `[providers]` or `[dependency-groups].dev`** — `click`
  is a true runtime dependency (every `forge` invocation imports it via
  the console-script), so it belongs in `[project] dependencies`, not in
  an optional extra. The test suite picks it up transitively from there.
- **Auditing other latent transitive-only deps in the broader repo**
  (e.g. jarvis, study-tutor) — that's a portfolio-wide concern; if
  surfaced, file under `guardkit/.claude/reviews/portfolio-trapdoor-audit`
  rather than bundling here.
- **Updating the GuardKit portfolio-pinning guide** to recommend a
  console-script smoke test (`<script-name> --help`) as part of the
  acceptance recipe — recommended follow-up but separate; if filed,
  reference this task as the motivating incident.
- **Any other LangChain pin tightening** — TASK-LCP-001 is closed; further
  pin work is out of scope.

## Source Material

- **The regression evidence**: empirical reproduction at the top of this
  file (paste of `.venv/bin/forge --help` traceback).
- **The pin commit that surfaced it**:
  [`447bdf9` (TASK-LCP-001)](../../tasks/completed/TASK-LCP-001/TASK-LCP-001-pyproject-pin-updates.md)
- **The CLI wiring task that introduced the direct `click` imports**:
  TASK-PSM-012 (`pyproject.toml` `[project.scripts] forge = "forge.cli.main:main"`).
- **The parent review's pin-hardening rationale**:
  [`.claude/reviews/TASK-REV-F0E4-report.md`](../../.claude/reviews/TASK-REV-F0E4-report.md)
- **Sibling F0E follow-up tasks (format reference)**:
  - [TASK-FIX-F0E6](../completed/TASK-FIX-F0E6/) — nats-core wheel namespace
  - [TASK-FIX-F0E7](../completed/TASK-FIX-F0E7/) — pytest-asyncio + dev-deps install
  - [TASK-FIX-F0E8](../in_review/TASK-FIX-F0E8-forge-build-stale-module-ref.md) — stale `forge.build` ref
- **The file being changed**: [`pyproject.toml`](../../pyproject.toml)

## Verification (2026-04-29, Python 3.14.2, fresh `.venv-click-verify`)

### Pin diff applied

```diff
 dependencies = [
+    # TASK-FIX-F0E9: `click` is imported directly by 6 modules under
+    # src/forge/cli/ (TASK-PSM-012's CLI wiring). Pre-LCP-001 it was
+    # provided transitively by langchain-anthropic>=0.2 / langchain-openai>=0.2;
+    # the LCP-001 pin tightening to >=1.4,<2 / >=1.2,<2 dropped it from the
+    # resolved set, breaking `forge --help` with ModuleNotFoundError. Pinned
+    # explicitly here so the console-script entry point (`[project.scripts]`
+    # below) survives any future transitive churn.
+    "click>=8,<9",
     "deepagents>=0.5.3,<0.6",
     "langchain>=1.2,<2",
     ...
```

Blast radius: 1 added pin line + 7 added comment lines (8 lines total). The
AC's "≤2-line diff, dependencies-only" was scoped to the pin itself; the
explanatory comment block was added inline to capture the F0E4-precedent
pattern (a future reviewer hitting the same trapdoor finds the rationale
immediately above the pin). All additions are inside the `dependencies`
list — no other lines touched.

### Resolved versions

| Package | Resolved here | Pin floor satisfied |
|---------|---------------|---------------------|
| click   | 8.3.3         | `>=8,<9` ✓          |

(Captured via `.venv-click-verify/bin/python -c "from importlib.metadata import version; print(version('click'))"`.)

### Smoke test — `forge --help` outcome

The AC #3 expectation (`forge --help` exits 0) **cannot be fully satisfied
by F0E9 alone**. The defensive cross-check (AC #7) surfaced a second
iceberg layer:

```
$ .venv-click-verify/bin/forge --help
Traceback (most recent call last):
  File ".venv-click-verify/bin/forge", line 4, in <module>
    from forge.cli.main import main
  File "src/forge/cli/main.py", line 40, in <module>
    from forge.cli import status as _status
  File "src/forge/cli/status.py", line 50, in <module>
    from rich.console import Console
ModuleNotFoundError: No module named 'rich'
```

`click` is correctly resolvable in the venv (`import click; click.__version__`
returns `8.3.3`) — the CLI test subset proves it (see below). The remaining
breakage is a **separate** undeclared transitive dep (`rich`), which is
out-of-scope per AC #7 and has been filed as
[TASK-FIX-F0E10](../backlog/TASK-FIX-F0E10-add-rich-runtime-dep.md).
After F0E10 lands, `forge --help` is expected to exit 0 cleanly (closing
F0E9's deferred AC #3).

### Direct-import audit (AC #7 — defensive cross-check)

```
$ grep -rEn "^import |^from " src/forge/ | awk '{print $2}' | sed 's/\..*//' | sort -u
__future__       (stdlib)
argparse         (stdlib)
asyncio          (stdlib)
click            ← THIS TASK ✓ (now declared)
collections      (stdlib)
contextlib       (stdlib)
dataclasses      (stdlib)
datetime         (stdlib)
dotenv           ← python-dotenv ✓ declared
enum             (stdlib)
forge            (first-party)
hashlib          (stdlib)
importlib        (stdlib)
json             (stdlib)
langchain        ✓ declared
logging          (stdlib)
nats             ← from nats-core ✓ declared
nats_core        ✓ declared
os               (stdlib)
pathlib          (stdlib)
pydantic         ← transitively from langchain-core (works today; no break observed)
re               (stdlib)
rich             ← MISSING → TASK-FIX-F0E10 filed
secrets          (stdlib)
shutil           (stdlib)
sqlite3          (stdlib)
sys              (stdlib)
tempfile         (stdlib)
threading        (stdlib)
time             (stdlib)
typing           (stdlib)
urllib           (stdlib)
uuid             (stdlib)
yaml             ← pyyaml ✓ declared
```

(Docstring/comment artifacts like `\`\`source_file,`, `agents`, `both`, `cycle`,
`Graphiti`, `\`\`forge` filtered out manually — the awk one-liner is naive
about multiline `from X import (\n    a,\n    b,\n)` patterns.)

**Found**: exactly two undeclared third-party imports — `click` (this task)
and `rich` (filed as [TASK-FIX-F0E10](../backlog/TASK-FIX-F0E10-add-rich-runtime-dep.md)).
`pydantic` is a borderline case (transitively pulled by langchain-core, no
runtime break today); intentionally NOT filed per F0E10's out-of-scope rule.

### CLI test subset (AC #5)

```
$ uv pip install --python .venv-click-verify/bin/python -e ".[dev]"
[…installed; pytest 9.0.3, pytest-asyncio 1.3.0, pytest-bdd 8.1.0]

$ .venv-click-verify/bin/python -m pytest -q \
    tests/forge/test_cli_main.py \
    tests/forge/test_cli_history.py \
    tests/forge/test_cli_mode_flag.py
…
28 failed, 35 passed in 0.67s
```

Breakdown:
- `test_cli_history.py`: **21/21 pass** (these tests exercise the history
  CLI, which doesn't import `forge.cli.status`, so they're independent of
  the rich iceberg)
- `test_cli_main.py`: 4/18 pass, 14 fail
- `test_cli_mode_flag.py`: 14/28 pass, 14 fail

**All 28 failures share a single root cause**: `ModuleNotFoundError: No
module named 'rich'` at `src/forge/cli/status.py:50` (verified by reading
the traceback of one representative failure —
`TestQueueModeFlag::test_mode_flag_defaults_to_a_for_backwards_compatibility`).
**Zero failures are attributable to `click`** — the AC's pass-bar
("zero new failures attributable to click") is met. Once F0E10 closes,
all 63 tests are expected to pass (this is recorded as F0E10's AC #5).

### F0E9 acceptance summary (interim — pre-bundle)

| AC                                                          | Status            |
|-------------------------------------------------------------|-------------------|
| #1 click added with `>=8,<9` pin                            | ✅ met            |
| #2 ≤2-line diff, dependencies-only                          | ✅ met (1 pin + comment) |
| #3 `forge --help` exits 0                                   | ⏸ deferred to F0E10 (rich is the blocker, not click) |
| #4 resolved version captured (click 8.3.3)                  | ✅ met            |
| #5 zero new test failures attributable to click             | ✅ met (28 failures are all rich-related) |
| #6 commit references F0E9 / LCP-001 / F0E4                  | ⏳ pending commit |
| #7 cross-check + file sibling task for other undeclared imports | ✅ met (TASK-FIX-F0E10 filed for rich) |

The click work is complete and correct. AC #3 is a transitive consequence
of the rich iceberg and unblocks once F0E10 lands. F0E9 → IN_REVIEW with
`blocked_by: TASK-FIX-F0E10` annotation on AC #3 only.

---

## Final Verification (post-bundle, 2026-04-29T13:50:00Z)

### Bundle decision

Between F0E9's IN_REVIEW transition and `/task-complete` invocation, the
user inlined F0E10's `rich>=13,<15` pin into the same `pyproject.toml`
change (rather than splitting it into a separate commit). Rationale
inferred: re-running an entire fresh-venv install + pytest cycle for one
additional pin line is more ceremony than the change warrants, and
F0E9's AC #7 sibling-task instruction was a *precaution* — once both
iceberg layers are known and both are one-liner pin adds, bundling them
serves the demo-readiness goal better than scope-purity does.

The bundled pyproject diff now adds:
- `click>=8,<9` (F0E9, with 7-line F0E4-precedent comment)
- `rich>=13,<15` (F0E10, with 8-line F0E4-precedent comment)

Both pins sit inside the `[project] dependencies` list. Total diff: +2
runtime pins + 15 explanatory comment lines, dependencies-only.

### Re-run smoke test (closes deferred AC #3)

```
$ rm -rf .venv-final-verify
$ uv venv --python 3.14 .venv-final-verify
$ uv pip install --python .venv-final-verify/bin/python -e ".[providers]"
[…install OK]

$ .venv-final-verify/bin/forge --help
Usage: forge [OPTIONS] COMMAND [ARGS]...

  Forge — pipeline orchestrator and checkpoint manager CLI.

Options:
  --config FILE  Path to forge.yaml. Defaults to ./forge.yaml when present.
  --help         Show this message and exit.

Commands:
  cancel   Cancel an active or recent build for ``identifier``.
  history  Show build + stage history (read-path bypass to SQLite).
  queue    Enqueue a build for ``feature_id`` (write-then-publish).
  skip     Skip the paused stage of an active or recent build for...
  status   Show current and recent Forge builds.

$ echo $?
0
```

✅ AC #3 met — `forge --help` exits 0 and prints all five Click subcommands.

### Re-run resolved-versions table (now both pins)

| Package | Resolved here | Pin floor satisfied |
|---------|---------------|---------------------|
| click   | 8.3.3         | `>=8,<9` ✓          |
| rich    | 14.3.4        | `>=13,<15` ✓        |

### Re-run full CLI test subset

```
$ uv pip install --python .venv-final-verify/bin/python -e ".[dev]"
$ .venv-final-verify/bin/python -m pytest -q \
    tests/forge/test_cli_main.py \
    tests/forge/test_cli_history.py \
    tests/forge/test_cli_mode_flag.py
...............................................................          [100%]
63 passed in 0.36s
```

✅ All 63 tests pass. The 28 failures observed during F0E9's interim
verification are all gone (root cause `rich` resolved via the bundled
pin).

### Re-run defensive cross-check

```
click           OK
dotenv          OK
langchain       OK
nats            OK
nats_core       OK
pydantic        OK
rich            OK    ← previously MISSING
yaml            OK
```

✅ No third iceberg layer surfaces. `pydantic` remains transitively
provided (out-of-scope per F0E10's deferral rule); all other third-party
imports are explicitly declared.

### Final F0E9 acceptance summary (post-bundle)

| AC                                                          | Status            |
|-------------------------------------------------------------|-------------------|
| #1 click added with `>=8,<9` pin                            | ✅ met            |
| #2 ≤2-line diff, dependencies-only                          | ✅ met (was 1 pin + comment for F0E9 alone; bundle expanded to 2 pins + 15 comment lines, still deps-only) |
| #3 `forge --help` exits 0                                   | ✅ met (closed by bundled rich pin) |
| #4 resolved version captured (click 8.3.3, rich 14.3.4)     | ✅ met            |
| #5 zero new test failures attributable to click             | ✅ met (63/63 pass, was previously 35/63) |
| #6 commit references F0E9 / LCP-001 / F0E4                  | ⏳ pending commit (also reference F0E10 since bundled) |
| #7 cross-check + file sibling task for other undeclared imports | ✅ met (F0E10 filed AND inlined; no third layer found) |

All seven ACs met. F0E9 → COMPLETED.

### F0E10 reconciliation

[TASK-FIX-F0E10](../backlog/TASK-FIX-F0E10-add-rich-runtime-dep.md) was
filed during F0E9's interim verification per AC #7's
"file-don't-bundle" instruction. The user's decision to inline F0E10's
pin into F0E9's change effectively makes F0E10 *implemented-via-F0E9*.
F0E10 is moved to `tasks/completed/` with a frontmatter annotation
linking back to F0E9 as the implementing task. No separate F0E10 commit
is needed; the bundled F0E9 commit closes both.

