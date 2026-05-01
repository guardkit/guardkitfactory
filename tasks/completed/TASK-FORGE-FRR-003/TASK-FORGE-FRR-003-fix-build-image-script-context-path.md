---
id: TASK-FORGE-FRR-003
title: Fix `scripts/build-image.sh` so `--build-context nats-core=../nats-core` resolves on the canonical sibling layout
status: completed
created: 2026-05-01T00:00:00Z
updated: 2026-05-01T11:40:00Z
completed: 2026-05-01T11:40:00Z
completed_location: tasks/completed/TASK-FORGE-FRR-003/
previous_state: in_review
state_transition_reason: "/task-complete — all quality gates passed (fast tier 3884/3884, integration 154/154+5 docker-gated skips)"
organized_files:
  - TASK-FORGE-FRR-003-fix-build-image-script-context-path.md
priority: high
task_type: fix
tags:
  - build
  - docker
  - buildx
  - scripts
  - feat-forge-009-followup
  - first-real-run-followup
  - quick-fix
complexity: 2
estimated_minutes: 45
estimated_effort: "30-45 minutes (one-line cd fix + comment rewrite + runbook sync)"
parent_feature: FEAT-FORGE-009
correlation_id: a58ec9a7-27c6-485a-beac-e18675639a10
discovered_on:
  date: 2026-05-01
  machine: GB10 (promaxgb10-41b1)
  context: "co-resident first walkthrough of jarvis FEAT-JARVIS-INTERNAL-001 runbook"
test_results:
  status: passed
  coverage: null  # minimal intensity — coverage not enforced
  last_run: 2026-05-01T11:35:00Z
  fast_tier: "3884 passed"
  integration_tier: "154 passed, 5 skipped (docker-gated slow tier)"
---

# Task: Fix `scripts/build-image.sh` so `--build-context nats-core=../nats-core` resolves on the canonical sibling layout

## Description

`scripts/build-image.sh` (the canonical Contract A producer for the
forge production image, FEAT-FORGE-009 / TASK-F009-005) is broken on
the canonical sibling layout. The script today does:

```bash
cd "$(dirname "$0")/../.."
# … then …
docker buildx build --build-context nats-core=../nats-core \
    -t forge:production-validation -f forge/Dockerfile forge/
```

Walking through the cd:

- The script lives at `forge/scripts/build-image.sh`.
- `dirname "$0"` → `forge/scripts/`.
- `forge/scripts/../..` → `forge/scripts/..` → `forge/` → `..` →
  forge's parent, e.g. `~/Projects/appmilla_github/`.

So buildx ends up running from `~/Projects/appmilla_github/`, and
`--build-context nats-core=../nats-core` — interpreted relative to
buildx's cwd — resolves to `~/Projects/nats-core`. **That directory
does not exist on the canonical layout** (where the canonical layout
is `~/Projects/appmilla_github/forge/` and
`~/Projects/appmilla_github/nats-core/` as siblings).

The script's leading comment block makes a confident claim that this
resolves correctly:

> The relative ``../nats-core`` path is interpreted relative to the
> directory ``docker buildx`` is invoked from — that's why this
> script changes to forge's PARENT directory before running buildx,
> regardless of where the operator invokes the script from.

That claim is wrong. From forge's PARENT, `../nats-core` resolves to
the GRANDPARENT's `nats-core`, not the SIBLING. The script's own
sanity-check at lines 45-50 (`[[ ! -d "./nats-core" ]]`) does verify
the sibling exists relative to forge's parent — i.e. it confirms
`appmilla_github/nats-core` is there — but that check passes, and
then buildx is invoked with `../nats-core` which is **not** the same
path as `./nats-core`. The check and the build-context arg disagree.

### Why this matters (empirical evidence — 2026-05-01 GB10 run)

During the jarvis FEAT-JARVIS-INTERNAL-001 first-real-run on 2026-05-01
on GB10 (correlation_id
`a58ec9a7-27c6-485a-beac-e18675639a10`), Phase 2.1 of the runbook
("forge image built") **could not be completed via the canonical
script**. The script's sanity-check at line 45 passed
(`./nats-core` was found, since `cd` had landed in `appmilla_github/`
and `nats-core` is a sibling of forge there), but buildx then failed
with:

```
failed to get build context nats-core: stat ../nats-core:
no such file or directory
```

Workaround applied: ran `docker buildx build --build-context
nats-core=../nats-core -t forge:production-validation -f Dockerfile .`
directly from inside `forge/` (so `../nats-core` resolves to the
sibling). Image built successfully and was retagged
`forge:latest` for runbook compatibility. 430MB.

This is a forge-side gap, not a jarvis-side one. The runbook's
Phase 2.1 ("`bash scripts/build-image.sh`") cannot be executed
verbatim today.

## Source code references

- [`scripts/build-image.sh`](../../../scripts/build-image.sh) — the
  whole file. Lines 31-38 are the cd block; line 62 is the buildx
  invocation; lines 1-29 are the leading comment block whose claim
  about path resolution is wrong.

## Goal

Pick **one** of the two correct invocations below, update the
script + comment block to match, and keep the corresponding runbook
invocation (`RUNBOOK-FEAT-FORGE-008-validation.md` and any F009
validation runbook) in sync so that the runbook's copy-paste line
and the script produce byte-identical buildx commands.

### Option A — cd into `forge/` (recommended)

```bash
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"   # → forge/
cd "$SCRIPT_DIR"

# …sanity checks against ../nats-core (the sibling)…
[[ -d "../nats-core" ]] || { echo "ERROR: …" >&2; exit 1; }
[[ -d "../nats-core/src/nats_core" ]] || { echo "ERROR: …" >&2; exit 1; }

docker buildx build \
    --build-context nats-core=../nats-core \
    -t forge:production-validation \
    -f Dockerfile .
```

Buildx runs from `forge/`, so `../nats-core` resolves to
`appmilla_github/nats-core` (sibling) ✓. The build-context path is
the **same string** the runbook documents and the operator on GB10
worked around with manually. `-f Dockerfile .` (without the
`forge/` prefix) is correct because we're already inside `forge/`.

### Option B — keep cd-to-parent, change the build-context arg

```bash
cd "$(dirname "$0")/../.."   # forge's parent

docker buildx build \
    --build-context nats-core=./nats-core \
    -t forge:production-validation \
    -f forge/Dockerfile forge/
```

Buildx runs from `appmilla_github/`, so `./nats-core` resolves
correctly. Keeps `-f forge/Dockerfile forge/` from the original
script. Less invasive but means the build-context path string
`./nats-core` is no longer copy-paste-equivalent to anything an
operator would type from inside `forge/`.

**Recommendation: Option A.** It minimises divergence between the
script's invocation and the operator's "from inside forge" mental
model, and the runbook's copy-paste line stays
operator-friendly.

Whichever option is picked, **the leading comment block must be
rewritten** to accurately describe what cwd buildx ends up
running from and why the relative `nats-core` path resolves
correctly. The current comment's "this is why we cd to forge's
PARENT directory" claim becomes false under Option A and remains
misleading even under Option B (you'd want
`./nats-core`, not `../nats-core`).

## Acceptance Criteria

- [ ] **Clean canonical-layout build succeeds**: on a host where
  `~/Projects/appmilla_github/forge/` and
  `~/Projects/appmilla_github/nats-core/` exist as siblings and
  nothing else is cd'd, running `bash
  ~/Projects/appmilla_github/forge/scripts/build-image.sh` from any
  cwd (e.g. from `/`, from `~/`, from `~/Projects/`) produces a
  successful image build and tags it as `forge:production-validation`
  without errors about `../nats-core` or `./nats-core` missing.
- [ ] **Script's leading comment block is accurate**: the comment
  block describes correctly (a) what cwd buildx ends up running
  from, (b) why the relative `nats-core` path resolves to the
  sibling, and (c) — crucially — does NOT make the false claim that
  `../nats-core` from forge's PARENT resolves to the sibling. If
  Option B is picked, the comment must reflect that the path string
  changed to `./nats-core`.
- [ ] **Sanity-check still works**: the early-exit sanity checks at
  current lines 45-56 (or their equivalent) still trigger if the
  sibling is missing, and they check the **same path** that buildx
  will use — i.e. if buildx will use `../nats-core`, the
  sanity-check must check `../nats-core`, not `./nats-core`. The
  current script's bug is partly that these two paths disagree.
- [ ] **Runbook line stays in sync**: any runbook that documents the
  buildx invocation literally —
  `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` §0.4 / §6.1
  per the script's own comment, plus any F009 validation runbook —
  must show the **exact same** `docker buildx build ...` line as
  the script. The script and the runbook should be byte-identical
  copy-paste pairs (LES1 §3 DKRX is the principle in play).
- [ ] **Operator instructions, when run verbatim, succeed**: a
  fresh-clone operator following only the runbook ("clone forge,
  clone nats-core as siblings, run `bash scripts/build-image.sh`")
  ends up with a tagged image and no error.
- [ ] **No regression on the existing layout assumption**: the
  script must still hard-fail with a clear error when the sibling
  layout is missing — better to fail at the entry point than deep
  inside the Dockerfile's COPY layer (this is the property the
  current sanity-checks at lines 45-56 were trying to provide).

## Out of Scope

- Switching to a different way of pulling `nats-core` into the
  build (e.g. publishing it to PyPI and `pip install`-ing it from
  there). That is a much bigger change and is tracked separately
  in `TASK-FIX-F0E6b-republish-nats-core-wheel.md`. This task only
  fixes the cwd / path bug in the existing buildx-build-context
  approach.
- Renaming `forge:production-validation` or removing the
  retag-to-`forge:latest` convention.
- Switching from `docker buildx` to plain `docker build`.
- Adding a `--from-host-network` flag or any other behavioural
  change beyond fixing the cwd / path mismatch.

## Implementation Notes

- **Recommend Option A** — see the rationale in the Goal section.
- **Verify the Dockerfile's `COPY --from=nats-core …` references**
  before changing the build-context arg's path string — under
  Option A or B the `nats-core` named-context is what the
  Dockerfile sees, and that's the same in both options. Only the
  flag's RHS changes.
- **Test on the canonical sibling layout first** (this is the
  documented one). If you can also test from a non-canonical layout
  (e.g. `forge/` and `nats-core/` not siblings, with operator using
  `--build-context nats-core=/some/abs/path`), document that as a
  recovery path in the comment block — but don't promise to support
  it in the script's automatic flow.
- **Don't lose the current sanity-check intent** — it's a good
  thing that the script fails fast with a readable error when the
  sibling is missing. Keep that, just make the path it checks
  match the path buildx will use.
- The script's current `SCRIPT_DIR` variable is computed but never
  used after the cd — useful for the error messages on lines
  46-47, so don't drop it; just recompute it post-cd if Option A
  changes its meaning.

## References

- **RESULTS file** that surfaced this issue:
  [/home/richardwoollcott/Projects/appmilla_github/jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md](../../../../jarvis/docs/runbooks/RESULTS-FEAT-JARVIS-INTERNAL-001-first-real-run.md)
- **Specific RESULTS table rows that motivate this task**:
  - Phase 2.1 (`forge image built`): "✅ with workaround.
    `forge:production-validation` (430MB, retagged `forge:latest`
    for runbook compat). `scripts/build-image.sh` is broken on this
    layout: it cd's to forge's parent and runs `--build-context
    nats-core=../nats-core`, which from the parent resolves to
    `~/Projects/nats-core` (does not exist). Worked around by
    running `docker buildx build --build-context
    nats-core=../nats-core -t forge:production-validation -f
    Dockerfile .` directly from inside `forge/`. Forge runbook
    gap-fold candidate, not jarvis."
  - Operator-side gaps row 3 (Phase 2.1): "Either fix the script to
    invoke buildx from inside `forge/` (so `../nats-core` resolves
    to the sibling), or change Phase 2.1 to invoke buildx
    directly. Forge-side gap."
  - Recommended follow-up #3: "forge: fix `scripts/build-image.sh`
    invocation path (run buildx from inside `forge/` not its
    parent)."
- **Forge source files**:
  - [`scripts/build-image.sh`](../../../scripts/build-image.sh) (the
    file this task fixes)
  - `Dockerfile` (the buildx target — confirm `COPY --from=nats-core
    …` lines stay valid under whichever option is picked)
  - `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` (the
    runbook whose §0.4 / §6.1 invocation must stay in sync —
    referenced by the script's own comment block at lines 19-22)
- **Run that surfaced this**:
  - **correlation_id**: `a58ec9a7-27c6-485a-beac-e18675639a10`
  - **Date**: 2026-05-01
  - **Machine**: GB10 (`promaxgb10-41b1`), co-resident first walkthrough

## Test Execution Log

### 2026-05-01 — /task-work execution (minimal intensity)

**Approach**: Option A from the Goal section — script cd's into `forge/`,
buildx invoked with `-f Dockerfile .`. Sanity checks now check
`../nats-core` (the same path buildx dereferences). Leading comment block
rewritten; `FORGE_DIR` variable now meaningfully used in the
sanity-check error messages. Drift-detector consumers (test constants
`CONTRACT_A_INVOCATION`, `CANONICAL_BUILDKIT`, `CANONICAL_INVOCATION`,
runbook §6.1, workflow comments) all updated in lockstep so the literal
`docker buildx build --build-context nats-core=../nats-core
-t forge:production-validation -f Dockerfile .` is byte-identical
across producer + consumers.

**Files changed**:

- `scripts/build-image.sh` — Option A applied, comment block rewritten,
  reference to "§0.4 / §6.1" narrowed to "§6.1" (§0.4 is the Python-env
  section, never referenced this invocation).
- `tests/dockerfile/test_install_layer.py` — `CONTRACT_A_INVOCATION`
  updated; `test_script_changes_to_forge_parent_directory` renamed to
  `test_script_changes_into_forge_directory` and regex updated to assert
  the one-parent-up cd pattern.
- `tests/integration/test_runbook_section6_fold.py` — `CANONICAL_BUILDKIT`
  updated; `test_runbook_section6_documents_parent_directory_cd`
  renamed to `test_runbook_section6_documents_forge_directory_cd` and
  prose check updated to look for "forge/" / "forge directory".
- `tests/integration/test_forge_production_image.py` —
  `CANONICAL_INVOCATION` updated.
- `docs/runbooks/RUNBOOK-FEAT-FORGE-008-validation.md` §6.1 — operator
  instruction now `cd ~/Projects/appmilla_github/forge` (not its parent)
  and buildx args match the script.
- `.github/workflows/forge-image.yml` — three comment blocks updated to
  describe Option A accurately. The actual `bash forge/scripts/build-image.sh`
  invocation is unchanged (still works because the sibling-checkout
  pattern still holds and the script is now cwd-independent).

**Path-resolution verification (dry-run from `/`)**:

```
Script invoked from: /
FORGE_DIR resolved to: /Users/richardwoollcott/Projects/appmilla_github/forge
After cd, pwd: /Users/richardwoollcott/Projects/appmilla_github/forge
Does ../nats-core exist? yes
Does ../nats-core/src/nats_core exist? yes
Resolved path: /Users/richardwoollcott/Projects/appmilla_github/nats-core
```

The script is cwd-independent: invoked from `/`, `~/`, or anywhere
else, it correctly resolves to `forge/` via `$0` and the sanity check
matches what buildx will dereference.

**Test results**:

- `pytest tests/dockerfile/test_install_layer.py
  tests/dockerfile/test_forge_image_workflow.py
  tests/integration/test_runbook_section6_fold.py
  tests/integration/test_forge_production_image.py
  tests/bdd/test_forge_production_image.py` — **89 passed, 4 skipped**
  (the 4 skips are `@slow` tests that require a running docker daemon).
- `pytest tests/ --ignore=tests/integration` — **3884 passed**.
- `pytest tests/integration/` — **154 passed, 5 skipped** (docker-gated).

**End-to-end docker build NOT executed in /task-work**: that's the
slow-tier `test_canonical_build_script_runs_to_a_tagged_image`
integration test, which will run on next CI invocation (or when an
operator runs `bash scripts/build-image.sh` with a docker daemon
present and the canonical sibling layout). The path-resolution dry-run
above plus the static drift-detector tests give high confidence the
build itself will succeed; the empirical workaround on GB10
(`docker buildx build --build-context nats-core=../nats-core -t
forge:production-validation -f Dockerfile .` from inside `forge/`,
which is byte-equivalent to what the fixed script now invokes) already
demonstrated that this exact buildx invocation produces a 430 MB
tagged image on the canonical layout.
