# Results: FEAT-FORGE-008 Validation

**Executed:** 2026-04-29 (single session, ~30 min)
**Operator:** Richard Woollcott (via Claude Code on `promaxgb10-41b1`)
**Commit at start:** `5e5cc73 Updated history` (`main` HEAD; `2f13eac` FEAT-FORGE-008 merge present in history)
**Host used:** `promaxgb10-41b1` is `127.0.0.1` per `/etc/hosts` — i.e. this *is* the GB10 host, so Phases 0–3 ran in the same environment. Phases 4–6 were not executed (see "Hard-stop" below).

## Hard-stop rationale

The runbook's own §1.3 pass criterion is:

> All Mode A tests green. **If any are red, FEAT-FORGE-008 broke the Mode A branch in `Supervisor.next_turn` — stop and triage immediately.**

Phase 1 produced two red Mode A integration tests with the exact regression signature §1.3 calls out (`Supervisor._dispatch` has no routing branch for `StageClass.TASK_REVIEW`). Per the runbook contract, later phases were not run because they would only add noise.

In addition, Phase 0.6's persistent JetStream-provisioned NATS does not exist on this host (no `nats.service`, no docker container with the standard streams pre-provisioned). A throwaway `nats:latest` was started for Phases 2–3 only; running the LES1 production-image gates (Phase 6) requires the canonical provisioned NATS plus a forge production Dockerfile (none ships in this repo).

## Per-gate outcomes

| Phase | Gate | Outcome | Evidence |
|-------|------|---------|----------|
| 0.1   | Working tree clean on `main`; FEAT-FORGE-008 merge `2f13eac` in history | ✅ | `git status` / `git log --oneline` |
| 0.2   | FEAT-FORGE-008 artefacts present (`.guardkit/features/FEAT-FORGE-008.yaml`, IMPLEMENTATION-GUIDE, `.feature` file) | ✅ | `ls` |
| 0.3   | Four new Mode B/C integration test files present | ✅ | `ls tests/integration/test_mode_*` |
| 0.4   | Editable install + dev/providers extras | ⚠️ | Existing user-site editable forge install pointed at deleted worktree `.guardkit/worktrees/FEAT-FORGE-005`; rewired with `pip install --user --break-system-packages --force-reinstall --no-deps -e .` after pip refused PEP 668 install. Plain `pip install -e '.[providers,dev]'` in a fresh venv FAILS because `nats-core>=0.2.0,<0.3` only resolves via `[tool.uv.sources]` (sibling `../nats-core`) which pip ignores — `uv` is required for the runbook command verbatim, but `uv` is not installed. |
| 0.5   | `forge queue --help` shows `--mode a\|b\|c` flag | ✅ | `forge queue --help` output |
| 0.6   | NATS reachable on host | ❌ | No `nats.service`, no NATS container running. Started ephemeral `nats:latest -js` for Phases 2–3 only. |
| 1.1   | Full pytest suite green | ❌ | `/tmp/forge-pytest-phase1.log` — 3757 passed, **4 failed**, 1 skipped (after `--ignore=tests/bdd/test_infrastructure_coordination.py`; that file has a hard collection error — see follow-up F008-VAL-001). |
| 1.2   | FEAT-FORGE-008 BDD bindings green | ✅ | `/tmp/forge-bdd-008.log` — 64 passed (runbook predicted 56). |
| 1.3   | Mode A regression byte-identical | ❌ | `/tmp/forge-mode-a-regression.log` — **2 failed / 40 passed**. Same root cause as 1.1: `Supervisor._dispatch` has no `StageClass.TASK_REVIEW` branch. |
| 2.2   | Mode A queue smoke (`forge queue ... --mode a`) | ✅ | `/tmp/forge-cli-mode-a.log` — `mode=mode-a`, correlation_id assigned. |
| 2.3   | Mode B queue smoke (NEW) | ✅ | `/tmp/forge-cli-mode-b.log` — `mode=mode-b`. |
| 2.4   | Mode B multi-feature reject (ASSUM-006) | ✅ | `/tmp/mb-multi-reject.log` — exit non-zero, error message cites "FEAT-FORGE-008 ASSUM-006: single feature per Mode B build". |
| 2.5   | Mode C queue smoke (NEW) | ⚠️ | `/tmp/forge-cli-mode-c.log` — works with a `FEAT-*` identifier. **`TASK-*` IDs are rejected** by wire-schema regex `^FEAT-[A-Z0-9]{3,12}$` in `nats_core.events._pipeline.BuildQueuedPayload`. Mode C accepting `TASK-*` per FEAT-FORGE-008 ASSUM-004 contradicts the wire schema. See follow-up F008-VAL-002. Evidence: `/tmp/forge-cli-mode-c-task.log`. |
| 2.6   | `forge history --mode a\|b\|c` filtering | ✅ | `/tmp/forge-cli-history-{a,b,c,all}.log` — each filter returns exactly the matching build; un-filtered returns all three. |
| 2.7   | Constitutional skip refusal (executor-layer) | ✅ | `/tmp/forge-constitutional.log` — 5/5 passed. |
| 3.1–3.2 | Pipeline `build-queued` event observed via `nats sub 'pipeline.>'` | ✅ | `/tmp/forge-nats-sub.log` — `pipeline.build-queued.FEAT-NATSCHECK` envelope captured; envelope-level `correlation_id` matches CLI-emitted UUID. |
| 3.3   | NATS routing + durable-decision integration tests | ✅ | 5/5 passed (`tests/integration/test_per_build_routing.py` + `test_durable_decision_on_publish_failure.py`). |
| 4.x–6.x | Checkpoint, degraded-mode, LES1 production-image gates | ⏸ deferred | Per Phase 1.3 hard-stop rule + Phase 0.6 prerequisite (no provisioned NATS, no forge `Dockerfile`). |
| 6.4   | Canonical-freeze walkthrough on clean MacBook + GB10 | ⏸ deferred | Cannot run a useful walkthrough until the four red gates are fixed and the runbook gaps in this RESULTS file are folded back. |

### Headline pytest failure modes (1.1)

```
FAILED tests/forge/adapters/test_sqlite_persistence.py::test_apply_at_boot_is_idempotent
  AssertionError: second apply must not duplicate the seed row
  rows == [(1,), (2,)] but expected [(1,)]
  → A new schema_version v2 row is inserted on every boot. The migration
    that adds v2 (almost certainly TASK-MBC8-001's mode column or
    TASK-MBC8-006's TASK_REVIEW/TASK_WORK stage entries) is non-idempotent.

FAILED tests/forge/test_approval_publisher.py::TestSingleOwnership
       ::test_no_other_module_in_forge_constructs_evidence_priors
  AssertionError: Other modules reconstruct details shape (AC-008):
    [PosixPath('src/forge/lifecycle/recovery.py')]
  → AC-008 of FEAT-FORGE-004 says only `approval_publisher.py` may
    construct the `evidence_priors` dict. FEAT-FORGE-008's recovery code
    open-codes the shape in lifecycle/recovery.py.

FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestMultiFeatureCatalogue
       ::test_three_features_produce_one_inner_loop_dispatch_each
FAILED tests/integration/test_mode_a_concurrency_and_integrity.py
       ::TestCorrelationThreading
       ::test_every_lifecycle_event_for_one_build_threads_one_correlation_id
  TypeError: Supervisor._dispatch: no routing for stage
            <StageClass.TASK_REVIEW: 'task-review'>
  → src/forge/pipeline/supervisor.py:1555. Mode A reaches `task-review`
    via the canonical model now that TASK_REVIEW was added to StageClass
    (TASK-MBC8-001), but the dispatch routing in `_dispatch` was only
    extended for the Mode-B/C-specific helpers. Mode A's path through
    `_dispatch` falls off the end and raises.
```

## Runbook gaps discovered during execution

These are the blocks that needed manual edits (per LES1 §8 — runbook copy-paste blocks are code).

| Phase | Block | What needed adjustment | Suggested runbook fix |
|-------|-------|------------------------|----------------------|
| 0.4   | `pip install -e '.[providers,dev]'` | Plain pip cannot resolve `nats-core>=0.2.0` because `[tool.uv.sources]` (sibling `../nats-core`) is `uv`-only. The runbook also needs to install `uv` first or call out the user-site rewire trick. PEP 668 also blocks the system-pip path on Ubuntu 24.04 unless `--break-system-packages` is used. | Pin to `uv pip install -e ".[providers,dev]"` and add an explicit "install `uv` first" step. Document the `--break-system-packages` fallback for non-uv flow. Also instruct operators to `pip install --user --force-reinstall --no-deps -e .` if a stale editable install points to a deleted worktree (the FEAT-FORGE-005 trap). |
| 0.5   | `which forge` | `forge` is installed by `pip install --user`, which puts the script in `~/.local/bin`. On a fresh shell that may not be on PATH. | Add `~/.local/bin` PATH check with the install instruction. |
| 0.6   | NATS reachability check | The runbook assumes a provisioned JetStream NATS is already up. There is none on this host. | Add a "if no NATS, run `docker run -d --network host nats:latest -js` for Phases 2–3" hint, OR link out to the actual nats-infrastructure provisioning runbook. Mark Phases 4+ as still requiring the *provisioned* server. |
| 2.x   | `--db-path "$FORGE_HOME/forge.db"` on `forge queue` | `forge queue` does not have `--db-path`; it reads `$FORGE_DB_PATH` env var or `forge.yaml`. `forge history` uses `--db` (not `--db-path`). `forge status` does have `--db-path`. | Replace the runbook's `--db-path "$FORGE_HOME/forge.db"` on every command with `export FORGE_DB_PATH="$FORGE_HOME/forge.db"` once at the top of Phase 2.1, then use the actual flag names per command. |
| 2.x   | `forge queue` invocations omit `--feature-yaml` and `--config` | `forge queue` requires `--feature-yaml FILE` (must exist on disk) and a `forge.yaml` (`--config FILE`). The runbook doesn't show how to produce either. | Have Phase 2.1 write a minimal `forge.yaml` (only `permissions.filesystem.allowlist` is mandatory) AND a per-feature stub YAML, and pass them via `--config` and `--feature-yaml`. Also, **Phase 2's claim that "this stubs NATS"** is **false** — `forge queue` always tries to publish to `$FORGE_NATS_URL` (default `nats://127.0.0.1:4222`). Either start a local NATS or set `FORGE_NATS_URL` to a fake-mode endpoint (which doesn't exist as a built-in seam). |
| 2.x   | Identifiers `FEAT-TEST-MA`, `FEAT-TEST-MB`, `TASK-TEST-MC` | The wire schema regex `^FEAT-[A-Z0-9]{3,12}$` rejects hyphenated suffixes (`FEAT-TEST-MA`) AND any non-`FEAT-` prefix. The CLI's `validate_feature_id` is more permissive than the payload's pydantic validator. | (a) Switch examples to `FEAT-TESTMA` / `FEAT-TESTMB` / `FEAT-TESTMC`. (b) File a real bug — Mode C is documented as accepting `TASK-*` but the payload schema forbids it (F008-VAL-002). |
| 1.3   | `tests/bdd/test_feat_forge_007.py` | File does not exist. The repo has `features/mode-a-greenfield-end-to-end/` but no Mode A BDD bindings module. | Drop the path from the runbook OR write the missing FEAT-FORGE-007 BDD bindings. |
| 1.1   | Full pytest sweep | `tests/bdd/test_infrastructure_coordination.py` fails to collect: `ModuleNotFoundError: No module named 'forge.build'` — TASK-IC-009/010 modules (`forge.build.git_operations`, `forge.build.test_verification`) were never landed. | Add `--ignore=tests/bdd/test_infrastructure_coordination.py` to Phase 1.1 with a footnote, OR file a substrate task to land TASK-IC-009/010. |
| 6.1   | `docker build -t forge:production-validation -f Dockerfile .` | No `Dockerfile` exists in the repo. | Either (a) create the production Dockerfile as part of the LES1 work, or (b) drop the runbook's claim that Phase 6 can run today. |

## Headline metrics

- **Test count:** 3757 passed / 4 failed / 1 skipped / 1 collection error (excluded with `--ignore`). Total ~3762 collected.
- **BDD scenarios (FEAT-FORGE-008):** 64/64 passed (runbook said 56; the count grew, no scenarios skipped).
- **Mode A integration (FEAT-FORGE-007 substrate guard):** 40/42 passed; the 2 reds match the runbook's predicted regression signature exactly.
- **Mode B/C integration (TASK-MBC8-010/011/013/014):** 68/68 passed.
- **Cross-mode concurrency assertion (TASK-MBC8-013):** ✅ pass.
- **Constitutional regression (executor-layer + prompt-layer):** 5/5 passed.
- **CLI surface:** `forge queue` accepts `--mode a|b|c`; `mode-c` queues for `FEAT-*` only (Mode C `TASK-*` rejected by wire schema); ASSUM-006 single-feature reject fires with the documented error message; `forge history --mode` filter works; `forge status` shows `mode-{a,b,c}` correctly.
- **NATS publish round-trip:** ✅ — `pipeline.build-queued.<feature>` envelope arrives with threaded `correlation_id` matching the CLI's emitted UUID.
- **LES1 production-image subscription / PORT matrix / ARFS / canonical-freeze walkthrough:** not attempted — see hard-stop and prerequisite gaps above.

## Decision

- [ ] Step 6 ✅ canonical — proceed to Step 7
- [x] **Step 6 partially passed — file follow-up tasks (linked below) and re-run blocked gates**
- [ ] Step 6 failed — block until issue resolved

The Mode A regression is a **hard regression in shipped FEAT-FORGE-007 substrate behaviour** introduced by FEAT-FORGE-008 — not a partial pass. Step 6 cannot be declared canonical until F008-VAL-003 lands. Mode B and Mode C themselves look healthy (Phase 2 + 68/68 integration tests + 64/64 BDD), so the fix scope is constrained: extend `Supervisor._dispatch` so Mode A can route through `StageClass.TASK_REVIEW` (the dispatcher most likely matches the existing subprocess/specialist family), then re-run Phase 1.

## Follow-up tasks

- **F008-VAL-001** — `tests/bdd/test_infrastructure_coordination.py` cannot collect. `forge.build.git_operations` and `forge.build.test_verification` (TASK-IC-009/010) were never landed in `src/forge/`. Either implement the missing modules or remove/skip the test. *Severity: medium (substrate, pre-existing — not introduced by FEAT-FORGE-008, but unblocks Phase 1.1's clean pass).*
- **F008-VAL-002** — Mode C wire-payload rejects `TASK-*` identifiers. `nats_core.events._pipeline.BuildQueuedPayload.feature_id` regex is `^FEAT-[A-Z0-9]{3,12}$` but FEAT-FORGE-008 ASSUM-004 says Mode C operates on `TASK-*` IDs. Either widen the regex (and rename the field to `subject_id`) or add a sibling `subject_id` field used by Mode C. *Severity: high — Mode C is half-shipped: CLI accepts the input, wire layer refuses it.*
- **F008-VAL-003** — `Supervisor._dispatch` raises `TypeError: no routing for stage <StageClass.TASK_REVIEW>` whenever Mode A reaches `task-review`. Add the routing branch in `src/forge/pipeline/supervisor.py:1555`. Re-run Phase 1.3 to confirm. *Severity: blocker — this is the FEAT-FORGE-007 substrate guard the runbook §1.3 calls out by name.*
- **F008-VAL-004** — `forge.lifecycle.recovery` violates the AC-008 single-ownership rule for `evidence_priors`. Move construction back into `forge.approval_publisher` or import the helper. *Severity: medium — the structural guard was deliberately wired during FEAT-FORGE-004; the recovery code's open-coded shape will drift on every future evidence-priors edit.*
- **F008-VAL-005** — `migrations.apply_at_boot` is non-idempotent for the v2 schema row. Audit the v2 migration that ships with FEAT-FORGE-008 (TASK-MBC8-001 mode column or the TASK_REVIEW/TASK_WORK seed) and gate the `INSERT INTO schema_version` on `WHERE NOT EXISTS`. *Severity: high — second boot duplicates a `schema_version` row, which then trips uniqueness or version-pin assertions downstream.*
- **F008-VAL-006** — Runbook gap-fold: apply every "Suggested runbook fix" from the table above to `RUNBOOK-FEAT-FORGE-008-validation.md` so the next walkthrough can run verbatim. *Severity: medium — LES1 §8 lesson; the runbook is the contract.*
- **F008-VAL-007** — Phases 4–6 prerequisites: provision the canonical NATS (JetStream streams + KV) on this host AND author the forge production `Dockerfile` so the LES1 CMDW/PORT/ARFS gates can run. *Severity: high — without these, Step 6 cannot be declared canonical even after F008-VAL-003 lands.*

## Hand-off notes for re-run

When F008-VAL-003 (Supervisor routing) and F008-VAL-005 (migration idempotency) land, re-run Phase 1 only — if those go green, the rest of Phase 1 (constitutional, BDD-008, Mode B/C integration) was already green this pass. Phase 2 needs no re-run beyond a quick smoke.

Phases 4–6 should not be attempted before F008-VAL-007 unprovisioned-NATS work lands — they will produce noise, not signal.
