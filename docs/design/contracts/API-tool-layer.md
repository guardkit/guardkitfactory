# API Contract — Tool Layer (`@tool(parse_docstring=True)`)

> **Type:** DeepAgents tool functions — schema-from-docstrings
> **Framework:** LangChain `@tool` decorator, DeepAgents 0.5.3 tool-layer conventions
> **Related ADRs:** [ADR-ARCH-004](../../architecture/decisions/ADR-ARCH-004-full-guardkit-cli-tool-surface.md), [ADR-ARCH-020](../../architecture/decisions/ADR-ARCH-020-adopt-deepagents-builtins.md), [ADR-ARCH-025](../../architecture/decisions/ADR-ARCH-025-tool-error-handling.md), [ADR-ARCH-031](../../architecture/decisions/ADR-ARCH-031-async-subagents-for-long-running-work.md)
> **Specialist rule:** langchain-tool-decorator-specialist — every tool wraps logic in try/except, returns a string, never raises.

---

## 1. Purpose

Every Forge-specific `@tool` is declared in this contract. DeepAgents built-ins (`write_todos`, `read_file`, `write_file`, `edit_file`, `ls`, `glob`, `grep`, `execute`, `task`, `interrupt`, Memory Store) are used as-is from DeepAgents 0.5.3 and not redeclared here (ADR-ARCH-020).

**Five tool groups:**

1. **Capability dispatch** — one generic tool for all fleet calls (ADR-ARCH-015).
2. **Approval + notification** — approval round-trip + notification emission.
3. **Graphiti** — learning-loop reads and writes.
4. **GuardKit** — one tool per GuardKit subcommand (ADR-ARCH-004).
5. **History** — SQLite writes.

Plus the five **AsyncSubAgent supervisor tools** exposed by DeepAgents middleware (`start_async_task`, `check_async_task`, `update_async_task`, `cancel_async_task`, `list_async_tasks` — ADR-ARCH-031). These are surfaced by DeepAgents and need no Forge declaration.

---

## 2. Universal Error Contract (ADR-ARCH-025)

Every `@tool` function:

- Returns `str` (JSON-encoded where structured — reasoning model parses).
- Wraps its entire body in `try / except Exception as exc:`.
- On failure, returns `f'{{"status":"error","error":"{type(exc).__name__}: {exc}"}}'`.
- NEVER raises. Adapter exceptions are converted at the tool boundary.
- Logs via `structlog` with `tool_name`, `duration_ms`, `status`.

This is asserted in the langchain-tool-decorator-specialist rule and the specialist-agent LES1 parity patterns.

---

## 3. Capability Dispatch

### 3.1 `dispatch_by_capability`

```python
@tool(parse_docstring=True)
async def dispatch_by_capability(
    tool_name: str,
    payload_json: str,
    intent_pattern: str | None = None,
    timeout_seconds: int = 900,
) -> str:
    """Resolve a fleet specialist for a capability and dispatch a typed command.

    The generic replacement for per-role dispatch tools (ADR-ARCH-015). Resolution
    uses exact tool-name match first, then intent-pattern fallback. Returns the
    specialist's ResultPayload as JSON, or a structured error if no agent
    resolves / the call times out.

    Args:
        tool_name: The ToolCapability.name the Forge wants invoked, e.g.
            "review_specification" or "generate_conversation_starter".
        payload_json: JSON string matching the target ToolCapability.parameters
            schema. Reasoning model assembles this from build context.
        intent_pattern: Optional intent pattern for fallback resolution when no
            exact tool match exists. Minimum confidence 0.7 required.
        timeout_seconds: Hard cut-off for the reply. Defaults to 900 (15 min).
            On breach, returns status=timeout and the caller decides what next.

    Returns:
        JSON string: ResultPayload on success; {"status":"error","error":"..."}
        on resolution or call failure.
    """
```

Implementation flow documented in [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md).

---

## 4. Approval + Notification

### 4.1 `request_approval`

```python
@tool(parse_docstring=True)
async def request_approval(
    build_id: str,
    stage_label: str,
    gate_mode: str,                                    # FLAG_FOR_REVIEW | HARD_STOP | MANDATORY_HUMAN_APPROVAL
    coach_score: float | None,
    rationale: str,
    details_json: str,
) -> str:
    """Pause the build and request Rich's approval via NATS + LangGraph interrupt().

    Publishes ApprovalRequestPayload to agents.approval.forge.{build_id}, marks
    the build PAUSED in SQLite, then calls LangGraph interrupt(). On resume, the
    value arrives as dict under server mode — this function rehydrates it via
    forge.adapters.langgraph.resume_value_as before returning.

    Args:
        build_id: The running build's ID (from SQLite builds.build_id).
        stage_label: Reasoning-model-chosen label for the stage being gated.
        gate_mode: One of FLAG_FOR_REVIEW, HARD_STOP, MANDATORY_HUMAN_APPROVAL.
        coach_score: Score from the dispatched specialist, or None in degraded mode.
        rationale: Reasoning-model's explanation of why this gate fired.
        details_json: JSON blob matching ApprovalRequestPayload.details convention
            (see API-nats-approval-protocol.md §3.2).

    Returns:
        JSON string with decision, responder, reason — the rehydrated
        ApprovalResponsePayload as dict.
    """
```

### 4.2 `emit_notification`

```python
@tool(parse_docstring=True)
async def emit_notification(
    channel: str,                                      # e.g. "jarvis.notification.telegram"
    subject: str,
    body: str,
    metadata_json: str = "{}",
) -> str:
    """Publish a NotificationPayload to a jarvis.notification.* channel.

    Used for AUTO_APPROVE stages — informational, not a gate. Reasoning model
    decides whether to notify based on retrieved Rich-ack-behaviour priors
    (ADR-ARCH-019 — no static notification config).

    Args:
        channel: Full NATS subject, e.g. "jarvis.notification.slack".
        subject: Short human-readable subject line.
        body: Longer body (markdown). Adapter renders per-transport.
        metadata_json: JSON blob of adapter-specific hints (priority, link, etc.).

    Returns:
        JSON string: {"status":"published","at":"<iso8601>"}.
    """
```

---

## 5. Graphiti

### 5.1 `record_override`

```python
@tool(parse_docstring=True)
async def record_override(
    build_id: str,
    stage_label: str,
    gate_mode_before: str,
    decision: str,
    rich_reason: str | None,
) -> str:
    """Record a human override on a gated stage in forge_pipeline_history.

    Used by learning loop to detect override patterns (e.g. "Rich overrode 6/10
    recent flag-for-reviews on review_architecture"). The CalibrationAdjustment
    entity is proposed separately — this tool only records the raw event.

    Args:
        build_id: The build where the override happened.
        stage_label: Reasoning-model-chosen label.
        gate_mode_before: What Forge chose (FLAG_FOR_REVIEW / HARD_STOP / …).
        decision: Rich's decision — approve / reject / defer / override.
        rich_reason: Optional reason text from ApprovalResponsePayload.reason.

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

### 5.2 `write_gate_decision`

```python
@tool(parse_docstring=True)
async def write_gate_decision(
    build_id: str,
    stage_label: str,
    decision_json: str,
) -> str:
    """Write a GateDecision (with evidence priors) to forge_pipeline_history.

    Every gate evaluation records why — the retrieved priors that informed it,
    the Coach score, the detection findings, and the chosen mode. This is the
    raw training data for future threshold calibration.

    Args:
        build_id: The build.
        stage_label: Reasoning-model-chosen label.
        decision_json: GateDecision.model_dump_json().

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

### 5.3 `read_override_history`

```python
@tool(parse_docstring=True)
async def read_override_history(
    capability: str,
    limit: int = 20,
    project_scope: str | None = None,
) -> str:
    """Retrieve recent override events for a capability from forge_pipeline_history.

    Reasoning model calls this to check "has Rich been overriding my gates on
    this capability lately?" — informs whether to auto-approve vs flag.

    Args:
        capability: e.g. "review_specification", "review_architecture".
        limit: How many recent overrides to return.
        project_scope: Filter to a project; None means fleet-wide.

    Returns:
        JSON array of {build_id, stage_label, gate_mode_before, decision,
        coach_score, timestamp}.
    """
```

### 5.4 `write_session_outcome`

```python
@tool(parse_docstring=True)
async def write_session_outcome(
    build_id: str,
    outcome: str,                                      # COMPLETE | FAILED | CANCELLED | SKIPPED
    summary_json: str,
) -> str:
    """Finalise the Graphiti record for a build — cross-references stage log.

    Called on terminal state transitions. Writes the high-level outcome node
    linking all the build's GateDecision + CapabilityResolution entities,
    plus PR URL and duration for future pattern mining.

    Args:
        build_id: The terminal build.
        outcome: Terminal status.
        summary_json: Build summary — duration, task counts, pr_url, error.

    Returns:
        JSON: {"status":"recorded","entity_id":"..."}.
    """
```

---

## 6. GuardKit Subcommand Tools

One `@tool` per GuardKit subcommand (ADR-ARCH-004). Each is a thin wrapper over DeepAgents `execute` that:

1. Assembles the subcommand + flags.
2. Reads `.guardkit/context-manifest.yaml` from the target repo to auto-derive `--context` flags (see [DDR-005](../decisions/DDR-005-cli-context-manifest-resolution.md)).
3. Pipes through `--nats` so GuardKit emits progress on `pipeline.stage-complete.*` directly.
4. Parses the GuardKit progress stream and surfaces artefact paths in the return value.

### 6.1 Tool list

| Tool | Wraps | Parameters |
|---|---|---|
| `guardkit_system_arch` | `guardkit system-arch` | repo, feature_id, scope |
| `guardkit_system_design` | `guardkit system-design` | repo, focus, protocols |
| `guardkit_system_plan` | `guardkit system-plan` | repo, feature_description |
| `guardkit_feature_spec` | `guardkit feature-spec` | repo, feature_description, context_paths |
| `guardkit_feature_plan` | `guardkit feature-plan` | repo, feature_id |
| `guardkit_task_review` | `guardkit task-review` | repo, task_id |
| `guardkit_task_work` | `guardkit task-work` | repo, task_id |
| `guardkit_task_complete` | `guardkit task-complete` | repo, task_id |
| `guardkit_autobuild` | `guardkit autobuild` | repo, feature_id |
| `guardkit_graphiti_add_context` | `guardkit graphiti add-context` | doc_path, group |
| `guardkit_graphiti_query` | `guardkit graphiti query` | query, group |

All share a common docstring pattern:

```python
@tool(parse_docstring=True)
async def guardkit_feature_spec(
    repo: str,
    feature_description: str,
    context_paths: list[str] | None = None,
) -> str:
    """Run `guardkit feature-spec` in the target repo with NATS streaming.

    Args:
        repo: Absolute path to the target repo (worktree root).
        feature_description: One-line description for the /feature-spec session.
        context_paths: Optional explicit --context overrides. When None, the
            context-manifest resolver picks them automatically.

    Returns:
        JSON: {"status":"success|failed","artefacts":["..."],"coach_score":...,
        "duration_secs":...,"stderr":"..."} — see API-subprocess.md §4 for
        the full result schema.
    """
```

---

## 7. History Tools

### 7.1 `record_build_transition`

```python
@tool(parse_docstring=True)
async def record_build_transition(
    build_id: str,
    to_status: str,
    fields_json: str = "{}",
) -> str:
    """Transition a build's status in SQLite and validate against state machine.

    Thin wrapper — the reasoning model uses this when it's making an explicit
    lifecycle transition (PREPARING → RUNNING, RUNNING → FINALISING, etc.).
    Terminal transitions trigger forge.adapters.nats to ack the JetStream message.

    Args:
        build_id: Build to transition.
        to_status: One of the BuildStatus enum values.
        fields_json: Extra fields to update (pr_url, error, worktree_path, etc.).

    Returns:
        JSON: {"status":"transitioned","from":"RUNNING","to":"FINALISING"}.
    """
```

### 7.2 `record_stage`

```python
@tool(parse_docstring=True)
async def record_stage(
    build_id: str,
    stage_label: str,
    target_kind: str,
    target_identifier: str,
    status: str,
    coach_score: float | None,
    gate_mode: str | None,
    duration_secs: float,
    details_json: str,
) -> str:
    """Write a StageLogEntry to SQLite after a dispatch completes.

    The reasoning model calls this after every dispatch — the emergent stage_label
    is what Rich reads in `forge history`. target_kind is one of:
    local_tool / fleet_capability / subagent.

    Args:
        build_id: Build that produced this stage.
        stage_label: Reasoning-model-chosen human-readable label.
        target_kind: local_tool | fleet_capability | subagent.
        target_identifier: tool name, agent_id:tool_name, or subagent name.
        status: PASSED | FAILED | GATED | SKIPPED.
        coach_score: Score if produced; None in degraded mode.
        gate_mode: Gate mode if gated; None for plain PASSED/FAILED stages.
        duration_secs: Wall-clock duration.
        details_json: Rationale + priors + findings as JSON.

    Returns:
        JSON: {"status":"recorded","stage_id":123}.
    """
```

---

## 8. Async-Subagent Supervisor Tools (DeepAgents)

Per ADR-ARCH-031, exposed by DeepAgents `AsyncSubAgentMiddleware` — not redeclared here. Usage contracts:

| Tool | Called by Forge when |
|---|---|
| `start_async_task` | Launching `autobuild_runner` for a build |
| `check_async_task` | Deciding "should I continue waiting or proceed?" |
| `update_async_task` | Rich injects "stop after current wave" via approval override |
| `cancel_async_task` | Responding to `forge cancel` CLI command |
| `list_async_tasks` | Serving `forge status` live progress view |

The `async_tasks` state channel is the contract boundary — see [DDR-006-async-subagent-state-channel-contract.md](../decisions/DDR-006-async-subagent-state-channel-contract.md).

---

## 9. Related

- Dispatch contract: [API-nats-agent-dispatch.md](API-nats-agent-dispatch.md)
- Approval contract: [API-nats-approval-protocol.md](API-nats-approval-protocol.md)
- Subagents: [API-subagents.md](API-subagents.md)
- Subprocess wrapper: [API-subprocess.md](API-subprocess.md)
- Data models: [DM-gating.md](../models/DM-gating.md), [DM-build-lifecycle.md](../models/DM-build-lifecycle.md)
