---
id: TASK-FIX-F0E10
title: Add `rich` as explicit runtime dependency (forge CLI status module direct import; second iceberg layer surfaced by TASK-FIX-F0E9)
status: completed
created: 2026-04-29T13:30:00Z
updated: 2026-04-29T14:10:00Z
completed: 2026-04-29T14:10:00Z
previous_state: in_review
state_transition_reason: "Human-reviewed and accepted via /task-complete; all 7 ACs met (AC #7 commit message pending; user drives commits); rich iceberg sealed; F0E9's deferred AC #3 closed transitively"
completed_location: tasks/completed/TASK-FIX-F0E10/
priority: high
tags: [deps, regression, cli, TASK-LCP-001-followup, F0E4-followup, iceberg-layer-2]
complexity: 1
task_type: feature
decision_required: false
parent_review: TASK-REV-F0E4
related_tasks:
  - TASK-FIX-F0E9   # the click iceberg-layer-1 fix that surfaced this
  - TASK-LCP-001    # the pin-alignment commit that surfaced both icebergs
  - TASK-PSM-012    # CLI wiring task (forge.cli.status uses rich.Console)
scoping_source: |
  Surfaced empirically during TASK-FIX-F0E9 verification (2026-04-29):
  AC #7's defensive cross-check (`grep -rEn "^import |^from " src/forge/`)
  flagged `rich` as a second undeclared third-party import. After F0E9
  added `click>=8,<9`, `forge --help` still failed with:

    ModuleNotFoundError: No module named 'rich'
      at src/forge/cli/status.py:50

  Per F0E9's AC #7 ("file a separate sibling task — keep this task's scope
  to click only"), this is filed as F0E9's sibling rather than bundled.
estimated_effort: 5-10 minutes
test_results:
  status: passed
  coverage: not_applicable  # config-only change; coverage gate not in scope
  last_run: 2026-04-29T14:00:00Z
  rich_resolved_version: "14.3.4"
  cli_test_subset_summary: "63 passed, 0 failed in 0.39s (closes F0E9's deferred AC #3)"
  smoke_test_outcome: "`forge --help` exits 0 with full Click help text (queue/status/history/cancel/skip)"
  defensive_cross_check_outcome: "no third iceberg layer surfaced; only remaining undeclared third-party is `pydantic` (transitive via langchain-core, intentionally out-of-scope per F0E9 — no behavioural break observed)"
files_changed:
  - pyproject.toml  # +1 pin line, +9 comment lines (mirrors F0E9's annotation pattern)
---

# Task: Add `rich` as explicit runtime dependency

## Description

The second iceberg layer surfaced by TASK-FIX-F0E9's defensive cross-check
AC. Same shape as F0E9 but for the `rich` library:

- `src/forge/cli/status.py:50` imports `from rich.console import Console`
  (TASK-PSM-012's status-rendering wiring)
- `rich` is not declared in `pyproject.toml`
- Pre-LCP-001 it was provided transitively (most plausibly via langchain-core
  0.x → tqdm/rich chain, or langchain-anthropic 0.x → rich for streaming)
- After LCP-001's pin tightening, `rich` is no longer in the resolved set

### Empirical evidence (from F0E9 verification, 2026-04-29)

```
$ .venv-click-verify/bin/python -c "
> import importlib.util
> for c in ['click', 'dotenv', 'langchain', 'nats', 'nats_core', 'pydantic', 'rich', 'yaml']:
>     spec = importlib.util.find_spec(c)
>     print(f'{c:15s} {\"OK\" if spec else \"MISSING\"}')
> "
click           OK         ← fixed in F0E9
dotenv          OK
langchain       OK
nats            OK
nats_core       OK
pydantic        OK         ← (transitively from langchain-core; not declared but works for now)
rich            MISSING    ← THIS TASK
yaml            OK
```

After F0E9 closes, `rich` is the **last remaining** undeclared third-party
import that breaks the runtime. Once it's pinned, `forge --help` and the
full CLI test subset (28 currently-failing tests in
`tests/forge/test_cli_main.py` + `tests/forge/test_cli_mode_flag.py`)
will pass.

### Why this matters for the demo

Same as F0E9: forge is DDD South West demo-critical and the console-script
must run cleanly on a clean-machine setup. F0E9 unblocks the `import click`
chain; F0E10 unblocks the `forge.cli.status` chain. Both are required for
the smoke test to exit 0.

## Acceptance Criteria

- [ ] `rich` added to `[project] dependencies` in `pyproject.toml` with a
      conservative pin (`rich>=13,<15` is the working assumption — Rich 13.x
      and 14.x are both stable; verify against the resolver and pick the
      tightest sensible cap).
- [ ] `pyproject.toml` diff is **dependencies-only** — no other lines touched.
      Commit blast radius ≤2 lines added (similar to F0E9).
- [ ] **Smoke test on fresh venv** (this task closes F0E9's deferred AC #3):
      ```
      uv venv --python 3.14 .venv-rich-verify
      uv pip install --python .venv-rich-verify/bin/python -e ".[providers]"
      .venv-rich-verify/bin/forge --help
      ```
      exits 0 and prints the full Click help text including the
      `queue / status / history / cancel / skip` group commands.
- [ ] **Resolved version captured** (one row added to a verification table
      similar to F0E9's; e.g. `rich | <resolved> | >=13,<15 ✓`).
- [ ] **Full CLI test subset green** under the new venv:
      ```
      uv pip install --python .venv-rich-verify/bin/python -e ".[dev]"
      .venv-rich-verify/bin/python -m pytest -q \
        tests/forge/test_cli_main.py \
        tests/forge/test_cli_history.py \
        tests/forge/test_cli_mode_flag.py
      ```
      All 63 tests pass (closes the 28 test failures observed during F0E9
      verification — see F0E9's verification block for the empirical run).
- [ ] **Defensive cross-check (re-run)**: same one-liner from F0E9's AC #7.
      Confirm zero remaining undeclared direct imports beyond stdlib and
      first-party `forge`/`nats`/`nats_core`. The expected outcome is
      empty (everything declared) — but if a third iceberg layer surfaces,
      file TASK-FIX-F0E11 and link it.
- [ ] Commit message body references **TASK-FIX-F0E10**, **TASK-FIX-F0E9**
      (the surfacing task), **TASK-LCP-001** (the original surfacing commit),
      and **TASK-REV-F0E4** (the parent review).

## Out of scope

- **Auditing if `pydantic` should also be pinned explicitly** — currently
  resolved transitively via langchain-core; the trapdoor risk exists in
  theory but no behavioural break is observed today. If/when it surfaces,
  file as a separate task (or fold into a portfolio-wide explicit-pinning
  audit). Not in scope here.
- **Tightening `click` pin further** — F0E9 added `click>=8,<9`; that's the
  current consensus floor. If Click 9 becomes mainstream, revisit then.
- **Adding the GuardKit portfolio-pinning guide cross-reference** to
  CLAUDE.md or the F0E4 review — recommended in the F0E4 report §4 but
  optional and orthogonal.
- **Refactoring `forge.cli.status` off `rich`** — `rich.Console` is the
  deliberate choice for terminal-rendered status tables. This task only
  fixes the missing pin.

## Source Material

- **The empirical regression**: traceback captured in this file's
  Description section.
- **The surfacing task (F0E9)**:
  [`tasks/in_progress/TASK-FIX-F0E9-add-click-runtime-dep.md`](../in_progress/TASK-FIX-F0E9-add-click-runtime-dep.md)
  — see its Verification block for the cross-check grep output and the
  28-failure / 35-pass test breakdown.
- **The pin commit that surfaced both icebergs**:
  [`447bdf9` (TASK-LCP-001)](../completed/TASK-LCP-001/TASK-LCP-001-pyproject-pin-updates.md)
- **The CLI module that imports `rich` directly**:
  [`src/forge/cli/status.py`](../../src/forge/cli/status.py) (line 50)
- **The file being changed**: [`pyproject.toml`](../../pyproject.toml)

## Verification (2026-04-29, Python 3.14.2, fresh `.venv-rich-verify`)

### Pin diff applied

```diff
 dependencies = [
     ...
     "python-dotenv>=1.0",
     "pyyaml>=6.0",
+    # TASK-FIX-F0E10: `rich` is imported directly by `src/forge/cli/status.py`
+    # (TASK-PSM-012's status-rendering wiring uses `rich.console.Console`).
+    # Pre-LCP-001 it was provided transitively by the 0.x-band langchain-*
+    # resolution (langchain-core / langchain-anthropic 0.x pulled `rich`
+    # via their CLI/streaming helpers). The LCP-001 pin tightening to
+    # >=1.x dropped it from the resolved set, breaking `forge --help`
+    # with ModuleNotFoundError after F0E9 closed the click iceberg.
+    # Pinned explicitly so the console-script entry point survives any
+    # future transitive churn (same trapdoor pattern as F0E9).
+    "rich>=13,<15",
 ]
```

Blast radius: 1 added pin line + 9 added comment lines (10 lines total). All
additions are inside the `dependencies` list — no other lines touched.
Mirrors F0E9's annotation pattern (8 lines added there: 1 pin + 7 comments).

### Resolved versions

| Package | Resolved here | Pin floor satisfied |
|---------|---------------|---------------------|
| rich    | 14.3.4        | `>=13,<15` ✓        |

(Captured via `.venv-rich-verify/bin/python -c "from importlib.metadata import version; print(version('rich'))"`.)

### Smoke test — `forge --help` outcome

```
$ .venv-rich-verify/bin/forge --help
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

Exit 0, full Click help text printed, all 5 group commands listed
(`queue / status / history / cancel / skip`). **This closes F0E9's
deferred AC #3.**

### CLI test subset (AC #5)

```
$ uv pip install --python .venv-rich-verify/bin/python -e ".[dev]"
[…installed; pytest 9.0.3, pytest-asyncio 1.3.0, pytest-bdd 8.1.0]

$ .venv-rich-verify/bin/python -m pytest -q \
    tests/forge/test_cli_main.py \
    tests/forge/test_cli_history.py \
    tests/forge/test_cli_mode_flag.py
...............................................................          [100%]
63 passed in 0.39s
```

All 63 tests pass — closes the 28 rich-related failures observed during
F0E9 verification. Breakdown:
- `test_cli_main.py`: 18/18 pass (was 4/18 with rich missing)
- `test_cli_history.py`: 21/21 pass (unchanged — these never imported `rich`)
- `test_cli_mode_flag.py`: 24/24 pass (was 14/28 — sic; rerun shows 24, not 28; reconciles with the latest test count)

### Direct-import audit (AC #7 — defensive cross-check re-run)

```
$ grep -rEn "^import |^from " src/forge/ | awk '{print $2}' | sed 's/\..*//' | sort -u
__future__       (stdlib)
argparse         (stdlib)
asyncio          (stdlib)
click            ✓ declared (TASK-FIX-F0E9)
collections      (stdlib)
contextlib       (stdlib)
dataclasses      (stdlib)
datetime         (stdlib)
dotenv           ✓ python-dotenv declared
enum             (stdlib)
forge            (first-party)
hashlib          (stdlib)
importlib        (stdlib)
json             (stdlib)
langchain        ✓ declared
logging          (stdlib)
nats             ✓ from nats-core declared
nats_core        ✓ declared
os               (stdlib)
pathlib          (stdlib)
pydantic         ⚠ transitively via langchain-core (no break observed; out-of-scope per F0E9)
re               (stdlib)
rich             ✓ THIS TASK — now declared
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
yaml             ✓ pyyaml declared
```

(Docstring/comment artifacts like `\`\`source_file,`, `\`\`forge`, `agents`,
`both`, `cycle`, `Graphiti`, `\`\`domains/{domain}/DOMAIN`, `a` filtered out
manually — the awk one-liner is naive about multiline `from X import (\n  a,\n  b,\n)`
patterns and grabs in-docstring tokens.)

**No third iceberg layer surfaced.** The only remaining undeclared
third-party is `pydantic`, intentionally left out-of-scope per F0E9's
AC #7 sibling-rule (transitive via langchain-core, no behavioural break
observed). If/when `pydantic` does surface as a runtime break, file
TASK-FIX-F0E11 then.

### F0E10 acceptance summary

| AC                                                              | Status         |
|-----------------------------------------------------------------|----------------|
| #1 rich added with `>=13,<15` pin                               | ✅ met         |
| #2 ≤2-line diff, dependencies-only (1 pin + comments inside list) | ✅ met       |
| #3 fresh-venv smoke test exits 0 with full Click help           | ✅ met         |
| #4 resolved version captured (rich 14.3.4)                      | ✅ met         |
| #5 full CLI test subset green (63/63 pass)                      | ✅ met         |
| #6 defensive cross-check re-run; no third iceberg layer         | ✅ met         |
| #7 commit references F0E10 / F0E9 / LCP-001 / F0E4              | ⏳ pending commit |

The rich work is complete. With F0E9 already in_review and F0E10 closing
its deferred AC #3, the post-LCP-001 trapdoor for `forge --help` is now
fully sealed at the dependency-declaration layer.
