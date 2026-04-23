# API Contract — Forge CLI (Click)

> **Type:** Human-facing command-line interface
> **Framework:** Click
> **Process model:** Short-lived (runs, reads/writes, exits — not a daemon)
> **Related ADRs:** [ADR-ARCH-013](../../architecture/decisions/ADR-ARCH-013-cli-read-bypasses-nats.md), [ADR-ARCH-012](../../architecture/decisions/ADR-ARCH-012-no-mcp-interface.md)

---

## 1. Purpose

`forge` is Rich's primary interface to the pipeline. It is intentionally small: five commands covering queue (write), status + history (read), cancel (write), skip (write). Everything else goes through Jarvis or NATS directly.

**Split IO:**

- **Read path** → SQLite direct. No NATS round-trip, no Forge process required (ADR-ARCH-013).
- **Write path** → NATS publish to the appropriate subject. The running Forge process consumes.

---

## 2. Command Inventory

| Command | Read/Write | Subject (if write) | Purpose |
|---|---|---|---|
| `forge queue` | Write (NATS) | `pipeline.build-queued.{feature_id}` | Enqueue a new build |
| `forge status` | Read (SQLite) | — | Show current + recent builds |
| `forge history` | Read (SQLite) | — | Show build + stage history |
| `forge cancel` | Write (NATS) | `agents.command.forge` with tool=`forge_cancel` | Cancel running/paused build |
| `forge skip` | Write (NATS) | `agents.command.forge` with tool=`forge_skip` | Skip a single flagged stage, continue build |

---

## 3. `forge queue`

### 3.1 Synopsis

```bash
forge queue <feature_id> --repo <path> [--branch <name>] \
    [--feature-yaml <path>] [--max-turns N] [--timeout SECONDS]
```

### 3.2 Flags

| Flag | Required | Default | Notes |
|---|---|---|---|
| `feature_id` (positional) | ✓ | — | e.g. `FEAT-A1B2` |
| `--repo` | ✓ | — | Absolute or `~/…` path to local clone |
| `--branch` | — | `main` | Base branch for build worktree |
| `--feature-yaml` | — | `<repo>/features/<feature_id>/feature.yaml` | Validated against allowlist |
| `--max-turns` | — | from `forge.yaml.defaults.max_turns` (5) | Passed through to `BuildQueuedPayload` |
| `--timeout` | — | from `forge.yaml.defaults.sdk_timeout` (1800) | Passed through |
| `--correlation-id` | — | auto-generated UUID | Override only for reruns |

### 3.3 Behaviour

1. Build `BuildQueuedPayload` with `triggered_by="cli"`, `originating_adapter="terminal"`, `originating_user=os.getlogin()`, `queued_at=datetime.now(UTC)`.
2. Wrap in `MessageEnvelope(source_id="forge-cli", event_type=EventType.BUILD_QUEUED, ...)`.
3. Publish to `pipeline.build-queued.{feature_id}` (via `nats-core.NATSClient`).
4. Write placeholder row to SQLite `builds` (status=`QUEUED`) so `forge status` shows it even before Forge picks it up.
5. Print `Queued FEAT-A1B2 (build pending) correlation_id=<uuid>` and exit 0.

**Exit codes:** `0` success, `1` NATS publish failure, `2` path outside allowlist, `3` duplicate feature_id already QUEUED/RUNNING/PAUSED.

---

## 4. `forge status`

### 4.1 Synopsis

```bash
forge status [<feature_id>] [--json] [--watch] [--full]
```

### 4.2 Behaviour

- Queries SQLite `builds` directly via `forge.adapters.sqlite.read_status()`.
- Default view: active builds (status IN `QUEUED`, `PREPARING`, `RUNNING`, `PAUSED`, `FINALISING`) + last 5 terminal ones.
- With `<feature_id>`: shows all builds for that feature, most recent first.
- `--watch`: polls every 2s, re-renders (uses `rich.live`).
- `--json`: emits JSON array of build rows (for piping into tooling).
- `--full`: includes `stage_log` entries per build (default: last 5 stages).

### 4.3 Output fields

```
BUILD                                            STATUS      STAGE                      STARTED        ELAPSED  SCORE
build-FEAT-A1B2-20260423170501                   RUNNING     Architecture Review        17:05:01       00:12:33 0.78
build-FEAT-C3D4-20260423140200  (paused)         PAUSED      Awaiting approval          14:02:00       03:18:12 0.52
```

### 4.4 Live autobuild progress

When the active build is running an `AsyncSubAgent` (autobuild_runner), `forge status` reads the `async_tasks` state channel via `list_async_tasks` per ADR-ARCH-031 and surfaces "Wave 2/4, 8/12 tasks done, est. 20 min remaining" as part of the STAGE cell.

---

## 5. `forge history`

### 5.1 Synopsis

```bash
forge history [--feature <feature_id>] [--limit N] [--since DATE] [--format table|json|md]
```

### 5.2 Behaviour

- `forge history` → last 50 builds.
- `forge history --feature FEAT-A1B2` → all builds for that feature, with `stage_log` expanded.
- `forge history --format md --since 2026-04-20` → markdown report suitable for Rich to paste into notes.

### 5.3 Markdown format

```markdown
# Forge history — FEAT-A1B2

## build-FEAT-A1B2-20260423170501 — COMPLETE (0h 42m)
Started: 2026-04-23 17:05:01 UTC
Finished: 2026-04-23 17:47:12 UTC
PR: https://github.com/appmilla/finproxy/pull/142

### Stages
- 17:05:03 — Retrieved priors (14 entities)            PASSED
- 17:05:47 — Build plan composed                       PASSED   score=0.84
- 17:06:15 — Architecture Review (architect-agent)     GATED    score=0.78  FLAG_FOR_REVIEW → approved by rich
- 17:12:04 — /feature-spec "login flow"                PASSED   score=0.82
- …
```

---

## 6. `forge cancel`

### 6.1 Synopsis

```bash
forge cancel <feature_id|build_id> [--reason "text"]
```

### 6.2 Behaviour

1. Resolve to a `build_id` via SQLite (pick the most recent non-terminal build for that feature).
2. Publish `CommandPayload(tool_name="forge_cancel", params={build_id, reason})` to `agents.command.forge`.
3. Subscribe to `agents.result.forge.{request_id}` with a short timeout (default 30s).
4. If reply received with `status="success"`, print confirmation.
5. If paused, Forge treats this as synthetic `ApprovalResponsePayload(decision="reject", responder="rich", reason="cli cancel")` — see [API-nats-approval-protocol.md §7](API-nats-approval-protocol.md#7-timeout-handling).

---

## 7. `forge skip`

### 7.1 Synopsis

```bash
forge skip <feature_id> [--reason "text"]
```

### 7.2 Behaviour

Only meaningful when the build is PAUSED on a `FLAG_FOR_REVIEW` gate. Publishes synthetic `ApprovalResponsePayload(decision="override", responder="rich", reason="cli skip")` to `agents.approval.forge.{build_id}.response` — graph resumes, specific stage is skipped, build continues.

If the build is not PAUSED, exits with error code and no NATS publish.

---

## 8. Shared Behaviour

### 8.1 Config loading

All commands load `forge.yaml` via `forge.config.load()`:

```python
@click.group()
@click.option("--config", default=None, help="Override forge.yaml path")
@click.pass_context
def forge(ctx, config):
    ctx.obj = AgentConfig.load(config)      # pydantic-settings; env vars override
```

### 8.2 Connection handling

- Read commands use `forge.adapters.sqlite.read_only_connect()` — no NATS connection at all.
- Write commands use `nats-core.NATSClient(config=AgentConfig.nats)` — connects, publishes, disconnects; exits cleanly.

### 8.3 Error presentation

CLI errors use Click's `ClickException` with `rich` formatting. Stack traces suppressed unless `--debug` flag is present.

### 8.4 Shell completion

Generated via `click.utils.get_app_dir` + `forge --install-completion`. Installs into shell rc file.

---

## 9. Multi-Tenancy

Project scoping is inferred from repo path:

```python
# forge.cli — project resolution
project = resolve_project_from_repo(repo_path)        # e.g. "finproxy"
topic = Topics.for_project(project, Topics.Pipeline.BUILD_QUEUED.format(feature_id=feature_id))
```

`forge status`/`history` filter SQLite rows by project when `--repo` is passed (default: all projects).

---

## 10. Related

- Pipeline events (what `forge queue` publishes): [API-nats-pipeline-events.md](API-nats-pipeline-events.md)
- SQLite schema (what reads consume): [API-sqlite-schema.md](API-sqlite-schema.md)
- Agent tools (what `forge_cancel`/`forge_skip` map to): [API-tool-layer.md](API-tool-layer.md)
- DDR: [DDR-005-cli-context-manifest-resolution.md](../decisions/DDR-005-cli-context-manifest-resolution.md)
