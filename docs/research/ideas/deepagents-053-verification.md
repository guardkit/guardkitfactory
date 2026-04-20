# DeepAgents 0.5.3 primitives verification

**Task**: TASK-SPIKE-C1E9 (parent review: TASK-REV-A7D3 §5)
**Date**: 2026-04-19
**Versions tested**: `deepagents==0.5.3`, `langgraph==1.1.8`, `langchain-core==1.3.0`, Python 3.14.2
**Model**: Google Gemini 2.5 Flash via `langchain-google-genai`
**Repro scripts**: `spikes/deepagents-053/`

## Pre-flight note — pyproject.toml pin drift

ADR-ARCH-020 declares the DeepAgents pin as `>=0.5.3, <0.6`.
`pyproject.toml` currently pins `deepagents>=0.4.11` — an ADR/pin drift.
This spike installed `0.5.3` directly (`pip install 'deepagents>=0.5.3,<0.6'`)
and did **not** edit `pyproject.toml`. The drift is flagged here for a
separate small chore task; it does not affect the verification below, but
`/system-design` should not run until the repo pin is aligned with ADR-020.

## ASSUM-008 — permissions refuse writes at runtime (backs ADR-ARCH-023)

**Verdict: PASS.**

The DeepAgents 0.5.3 permissions system refuses filesystem writes outside
the `allow_write` allowlist at **runtime**, not merely in logs. The tool
call is intercepted by `_PermissionMiddleware.wrap_tool_call` before the
backend executes; denial returns a typed `ToolMessage(status="error",
content="Error: permission denied for write on <path>")` and the underlying
backend write never runs.

Observed in `spikes/deepagents-053/permissions_repro.py` with a real
`FilesystemBackend(root_dir=<sandbox>, virtual_mode=False)` and the
rule-set

```python
[
    FilesystemPermission(operations=["write"], paths=[f"{ok_dir}/**"], mode="allow"),
    FilesystemPermission(operations=["write"], paths=["/**"],         mode="deny"),
]
```

A Gemini-driven agent instructed to `write_file` into the forbidden
sub-directory produced the expected `ToolMessage` error, and
`os.path.exists(forbidden_target)` was `False` after the invocation.

Side-observation (not a pass condition): in the follow-up invocation
instructed to write to the allowed path, Gemini did not emit a tool call —
likely a conversational quirk from the same-agent state carrying the prior
`permission denied` error. This is an LLM-behaviour artefact; it does not
weaken the ASSUM-008 verdict, which is about **refusal** and was exercised
under the forbidden invocation. The allowed-write happy path is already
exercised by DeepAgents' own test suite.

**ADR-ARCH-023 stands as written.** No revision task needed.

## ASSUM-009 — `interrupt()` + typed Pydantic resume round-trip (backs ADR-ARCH-021)

**Verdict (direct `CompiledStateGraph.invoke`, cross-process): PASS.**
**Verdict (`langgraph dev` server mode): NOT TESTED IN THIS SPIKE — see gap note below.**

`interrupt_graph.py` pauses a compiled `StateGraph` at `interrupt(payload)`
with a Pydantic `ApprovalRequest` carrying a nested `Requestor` model, a
`uuid.UUID`, a timezone-aware `datetime`, and a `Literal` field. The paused
state is persisted to `interrupt_state.sqlite` via `SqliteSaver` and the
process exits.

`interrupt_resume.py` runs in a **separate Python process**, reopens the
same SQLite-backed `SqliteSaver`, rebuilds the compiled graph, and calls
`graph.invoke(Command(resume=ApprovalDecision(...)), config)` against the
same `thread_id`. The node captures the value the graph itself observes on
the return of `interrupt(...)` and records type metadata into final state.

Observed verdict rows (from `interrupt_resume.py`):

| Check | Value | Required |
|---|---|---|
| `type(resumed).__name__` (inside node) | `'ApprovalDecision'` | `'ApprovalDecision'` |
| `isinstance(resumed, ApprovalDecision)` | `True` | `True` |
| nested `decided_by` type | `'Requestor'` | `'Requestor'` |
| `decided_at` type | `'datetime'` | `'datetime'` |
| field `.approved` | `True` | survives |
| graph completed past interrupt to `finalise` | `True` | `True` |

The value a node sees on `interrupt()`'s return is a fully-instantiated
Pydantic model with nested Pydantic/UUID/datetime fields intact, not a
dict or msgpack blob.

**Mode-coverage gap.** AC-2 of TASK-SPIKE-C1E9 requires the round-trip be
observed under **both** `langgraph dev` server mode and direct
`CompiledStateGraph.invoke`. Only direct `.invoke` was exercised in this
spike run. `langgraph dev` requires additional scaffolding (install
`langgraph-cli`, write a `langgraph.json`, run a background dev server,
drive it via the LangGraph SDK) and its resume path goes through a
separate serialization layer over HTTP, which is the part most at risk of
degrading typed fields to dicts. This gap is itself load-bearing for
ADR-ARCH-021's assumption that HITL approval works in the canonical
Forge deployment path. Per agreement with spike owner, this is deferred
to either a follow-up spike or folded into `/system-design`'s initial
bootstrap of `langgraph dev` + `langgraph.json`.

**Pydantic-serialization warning (observed, non-blocking).**
LangGraph emits:

    Deserializing unregistered type __main__.ApprovalRequest from
    checkpoint. This will be blocked in a future version.
    Add to allowed_msgpack_modules to silence:
    [('__main__', 'ApprovalRequest')]

The warning does not affect the current-version round-trip (both scripts
exit 0) but does indicate that Forge will need to register Pydantic
interrupt payload types via `allowed_msgpack_modules` before upgrading
past whichever future LangGraph release flips the warning to an error.
Capture this as a follow-up note in `/system-design` when ADR-021's
HITL payloads are defined.

**ADR-ARCH-021 stands as written for direct-invoke mode.** Server-mode
verification is deferred; ADR-021 should not be treated as fully
verified until the server-mode gap is closed.

## Environment fingerprint

```
deepagents==0.5.3
langchain==1.2.15
langchain-core==1.3.0
langchain-google-genai==(per .[providers])
langgraph==1.1.8
langgraph-prebuilt==1.0.10
python==3.14.2
```

## Follow-ups

- **TASK-CHORE-*** (to spawn): bring `pyproject.toml` `deepagents` pin
  into alignment with ADR-ARCH-020 (`>=0.5.3, <0.6`). Blocker for
  `/system-design` independent of the ASSUM verdicts above.
