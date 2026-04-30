# Results: FEAT-FORGE-008 Validation — Rerun (post-FEAT-F8 fan-out)

**Executed:** 2026-04-30 (single session, ~30 min)
**Operator:** Richard Woollcott (via Claude Code on `promaxgb10-41b1`)
**Commit at start:** `92ce8a4 docs(review): record TASK-REV-F008 architectural review + FEAT-F8 plan`
  (`main` HEAD; all FEAT-F8 Wave 1 + Wave 2 + Wave 3 commits in history — see `docs/reviews/REVIEW-F008-validation-triage.md` and the FEAT-F8 IMPLEMENTATION-GUIDE for the per-task list).
**Predecessor:** [`RESULTS-FEAT-FORGE-008-validation.md`](./RESULTS-FEAT-FORGE-008-validation.md) (2026-04-29) — "Step 6 partially passed" with 4 reds.
**Scope:** Phases 0–3 only. Phases 4–6 remain blocked on Wave 3 cross-repo prerequisites (FCH-001 in `nats-infrastructure`, FEAT-FORGE-009 production Dockerfile).

## Decision

**Step 6 ✅ canonical for Phases 0–3.** Step 7 (FinProxy first real run) is unblocked from forge's side. Phases 4–6 stay deferred until FCH-001 + FEAT-FORGE-009 land.

All four blockers from the 2026-04-29 walkthrough are green:

| 2026-04-29 finding | Wave-1/2 fix | 2026-04-30 status |
|---|---|---|
| F008-VAL-003 — `Supervisor._dispatch` no `TASK_REVIEW` route (2 Mode A reds) | TASK-F8-003 (`68adba9`) | ✅ Phase 1.3: 42/42 Mode A green |
| F008-VAL-004 — `recovery.py` open-codes `evidence_priors` (AC-008 reg) | TASK-F8-004 (`c9503f1`) | ✅ Phase 1.1: `test_approval_publisher.py` green |
| F008-VAL-005 — stale idempotency assertion (re-classified by review) | TASK-F8-005 (`8c06012`) | ✅ Phase 1.1: `test_sqlite_persistence.py` green |
| F008-VAL-002 — Mode C wire-schema rejects `TASK-*` | TASK-F8-002 (`8ef2c3e` + nats-core 0.3.0 `ae20423`) | ✅ Phase 2.5 + 3.2b: `task_id="TASK-NATSCHECKC"` round-trips through live NATS |
| F008-VAL-001 — `forge.build` modules missing | TASK-F8-001 (`d0c2f81`) | ✅ Phase 1.1: full sweep with NO `--ignore`, 3853 passed |
| F008-VAL-006 — runbook gap-fold | TASK-F8-006 (`35952fd`) | ✅ Phase 0.4/0.5/0.6/2.x folded; new gaps captured below |
| F008-VAL-007 — Phase 6 prerequisites | TASK-F8-007a (`1c005f5`/`118104c`) + TASK-F8-007b (`4d953cf`) | ⏸ Wave 3 delegated; Phase 4–6 stay deferred |

## Per-gate outcomes

| Phase | Gate | Outcome | Evidence |
|-------|------|---------|----------|
| 0.1 | Working tree clean on `main`; `2f13eac` in history | ✅ | `git status` / `git log --oneline -5` |
| 0.2 | FEAT-FORGE-008 artefacts present | ✅ | `ls .guardkit/features/FEAT-FORGE-008.yaml ...` |
| 0.3 | Four Mode B/C integration test files present | ✅ | `ls tests/integration/test_mode_*` |
| 0.4 | Editable install + extras | ✅ | Existing user-site editable install at `/home/richardwoollcott/.local/lib/python3.12/site-packages` resolves to live tree; `nats-core 0.3.0` importable; `pytest-asyncio 1.3.0` present. `uv` still not installed on this host — gap-fold §0.4 fallback applies. |
| 0.5 | `forge queue --help` shows `--mode [a\|b\|c]` | ✅ | `forge queue --help` output |
| 0.6 | NATS reachable | ✅ (throwaway) | Started `forge-rerun-nats` (host-network `nats:latest -js`) for Phases 2–3. JetStream listening on `:4222`. |
| 1.1 | Full pytest sweep (NO `--ignore`) | ✅ | `/tmp/forge-pytest-phase1.log` — **3853 passed, 1 skipped, 0 failed** in 7.33s |
| 1.2 | FEAT-FORGE-008 BDD bindings | ✅ | `/tmp/forge-bdd-008.log` — **64/64 passed** |
| 1.3 | Mode A regression | ✅ | `/tmp/forge-mode-a-regression.log` — **42/42 passed** (was 40/42 with the TASK_REVIEW dispatch reds) |
| 2.2 | Mode A queue smoke | ✅ | `/tmp/forge-cli-mode-a.log` — `Queued FEAT-TESTMA … mode=mode-a correlation_id=766a7fb6-…`; `status` shows `mode=mode-a`; `history` records the queue event |
| 2.3 | Mode B queue smoke | ✅ | `/tmp/forge-cli-mode-b.log` — `mode=mode-b` |
| 2.4 | Mode B multi-feature reject (ASSUM-006) | ✅ | exit 2 + `forge queue --mode b requires exactly one feature identifier (FEAT-FORGE-008 ASSUM-006: single feature per Mode B build)` |
| 2.5 | Mode C queue smoke (canonical TASK-* + parent_feature) | ✅ | `/tmp/forge-cli-mode-c.log` — `Queued FEAT-TESTMC … mode=mode-c` (resolved from `parent_feature` in the fix-task YAML); `status` shows `mode-c` |
| 2.5-N | Mode C negative paths | ✅ | FEAT-shaped positional → exit 4 with `Mode C requires positional argument to match ^TASK-[A-Z0-9]{3,12}$`; missing `parent_feature` → exit 2 with `Mode C requires the fix-task YAML to declare a non-empty 'parent_feature' field (string)` |
| 2.6 | Mode-filtered history | ✅ | `--mode b` → only FEAT-TESTMB; `--mode c` → only FEAT-TESTMC; no filter → all three |
| 2.7 | Constitutional skip refusal | ✅ | `/tmp/forge-constitutional.log` — 5/5 passed |
| 3.1–3.2 | NATS `pipeline.build-queued` round-trip + correlation thread (Mode B) | ✅ | `/tmp/forge-nats-pipeline.log` — envelope `correlation_id=7b39c6a1-…` matches CLI-emitted; payload `mode=mode-b`, `task_id=null` |
| 3.2b | Mode C wire round-trip (post-TASK-F8-002) | ✅ | same log — second envelope: `feature_id="FEAT-NATSCHECKC"`, `task_id="TASK-NATSCHECKC"`, `mode="mode-c"`, threaded `correlation_id=d4c9099e-…`. Bidirectional invariant (`mode==mode-c <=> task_id is not None`) satisfied. |
| 3.3 | per-build routing + durable-decision integration | ✅ | `/tmp/forge-routing.log` — 5/5 passed |
| 3.x | AC-10 Mode C wire-layer smoke | ✅ | `tests/integration/test_mode_c_wire_smoke_e2e.py` — 1/1 passed against live NATS (`FORGE_NATS_URL=nats://127.0.0.1:4222`) |
| 4.x–6.x | Checkpoint, degraded-mode, LES1 production-image gates | ⏸ deferred | Per Phase 0.6 prerequisite (no provisioned NATS — FCH-001 in `nats-infrastructure`) and Phase 6.1 prerequisite (no forge `Dockerfile` — FEAT-FORGE-009). |
| 6.4 | Canonical-freeze walkthrough | ⏸ deferred | Cannot run a useful Phase 6.4 sweep until FCH-001 + FEAT-FORGE-009 land. |

## Headline metrics

- **Test count:** 3853 passed / 0 failed / 1 skipped — **+96 passes** vs. 2026-04-29 baseline (3757p/4f/1s with `--ignore`).
- **BDD scenarios (FEAT-FORGE-008):** 64/64 passed (unchanged from AC-6 gate run).
- **Mode A integration:** 42/42 passed (was 40/42 — the two TASK_REVIEW reds resolved).
- **CLI surface:** `forge queue --mode {a,b,c}` all green; ASSUM-006 reject fires; Mode C accepts canonical `TASK-*` positional with `parent_feature` resolution.
- **NATS publish round-trip:** ✅ Mode B (`task_id=null`) **and** Mode C (`task_id="TASK-NATSCHECKC"`) both round-trip through live NATS with threaded `correlation_id`.

## Runbook gaps discovered during this rerun

These are the blocks that needed manual tweaks. Per LES1 §8, runbook copy-paste blocks are code; fold them back before declaring Phase 6.4 (full canonical-freeze walkthrough) complete.

| Phase | Block | What needed adjustment | Suggested runbook fix |
|-------|-------|------------------------|-----------------------|
| 2.x   | All `forge queue|status|history` invocations passed `--config "$FORGE_HOME/forge.yaml"` as a **subcommand** flag | `--config` is a top-level option (`forge --config FILE <subcommand>`); the subcommand parser rejects it. The runbook §2.2/2.3/2.5/2.6 all pass `--config` after the subcommand. | Move `--config` to between `forge` and the subcommand on every example, OR drop `--config` and rely on `./forge.yaml` auto-pickup (the loader picks it up from CWD when present). |
| 2.1   | `forge.yaml` example uses `~/Projects/appmilla_github/forge` in `permissions.filesystem.allowlist` | `ForgeConfig` validator requires absolute paths; `~` is not expanded. Fails fast with `ValidationError: filesystem.allowlist entries must be absolute paths`. | Use shell expansion in the heredoc (`- $HOME/Projects/appmilla_github/forge` with `<<EOF` not `<<'EOF'`) or hard-code `/home/<user>/Projects/...`. |
| 2.2   | `forge queue ... --repo guardkit/test-project` (Mode A) | `--repo` is `click.Path(exists=True)` so the runbook's placeholder string fails immediately. | Either point `--repo` at an existing checkout (e.g. the live forge tree, allowlisted) or pre-create an empty dir for the placeholder. |
| 2.2   | `forge queue ... --mode a` invocation omits `--feature-yaml` | Mode A also requires `--feature-yaml FILE` — the runbook claims it's only Mode B/C. The CLI rejects with `Error: Missing option '--feature-yaml'.` | Pass `--feature-yaml "$FORGE_HOME/feature-stub.yaml"` on Mode A too, OR widen the §2.1 stub creation step to apply across all three modes. |
| 3.1   | `nats sub 'pipeline.>' --headers --raw` | `--headers` is not a valid flag for the `nats` CLI on this host (v0.x). Subscriber dies immediately. The valid flag is `--headers-only`, but for our purposes plain `--raw` is sufficient. | Drop `--headers` from the §3.1 block. The envelope's `correlation_id` is in the JSON body, not in NATS headers, so `--raw` alone produces the assertion evidence we need. |

None of these gaps are correctness regressions in `forge`; all are documentation/copy-paste defects in the runbook itself. Filing follow-up TASK-F8-006-style runbook touch-up as next step (or fold into a Phase-6.4-prep PR).

## Cross-repo handoff state (Wave 3)

- **FCH-001** (NATS canonical provisioning) — filed in `nats-infrastructure` per `forge/docs/handoffs/F8-007a-nats-canonical-provisioning.md` (commits `1c005f5` + `118104c`). Cross-repo delivery on independent timeline. Phase 0.6 §"Phase scope of NATS requirement" → "Phases 4+ require canonically-provisioned JetStream — must be the provisioned server" remains the gate.
- **FEAT-FORGE-009** (forge production `Dockerfile` + `forge serve`) — scoped at `docs/scoping/F8-007b-forge-production-dockerfile.md` (commit `4d953cf`). Backlog handoff at `tasks/backlog/FEAT-FORGE-009-production-image.md`. Phase 6.1 (CMDW gate) stays structurally unreachable until this lands.

## Follow-up tasks (proposed)

- **F008-RERUN-001** — Apply the §"Runbook gaps discovered during this rerun" table to `RUNBOOK-FEAT-FORGE-008-validation.md` (5 small edits in §2.x and §3.1). Direct (docs); LES1 §8 contract.
- **F008-RERUN-002** — (optional) Walk through Phase 6.4 canonical-freeze on a clean MacBook **only after** FCH-001 + FEAT-FORGE-009 land and the runbook is folded. Single-session walkthrough logged in `command-history.md`.

## What was healthy (worth not re-checking on next pass)

- Substrate regression (Mode A, AC-008 single-ownership, schema-version idempotency) — all green from a fresh checkout.
- Wire-schema bidirectional invariant (`mode == "mode-c" <=> task_id is not None`) — enforced at the pydantic boundary, exercised end-to-end in 3.2b and AC-10 wire smoke.
- CLI/wire alignment for Mode C — the CLI emits `TASK-*` as the positional and the wire payload now carries it as a sibling field; no rebuilding required.

---

*Generated 2026-04-30 from a single-session rerun by Claude Code on `promaxgb10-41b1`. The accompanying runbook update (commit pending) lifts the `--ignore=tests/bdd/test_infrastructure_coordination.py` workaround in §1.1 since TASK-F8-001 landed.*
