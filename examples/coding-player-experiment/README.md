# Optional dcode Player

This experiment equips GuardKit's existing Player with dcode 0.1.69. GuardKit's
Coach, review rules and outer repair loop continue to decide whether the work
satisfies the task. The default native Player and Claude SDK route are unchanged.
Deterministic graph tests establish integration behavior, not coding quality or
an improvement in repair success. Codex still coordinates this work: M0 is nonzero.

## Prepare an isolated run

Use a private sandbox with Python 3.12 or newer, below Python 4, and install the
locked optional extra:

```sh
uv sync --locked --extra dcode
```

Ordinary installs still support Python 3.11 without importing or installing dcode.
The extra includes LangGraph API dependencies; use its separate experiment
environment rather than adding it to a serving environment.

Prepare the actual task worktree before selecting its harness. Reuse the unchanged
[`coding-skills-bundle`](../coding-skills-bundle/README.md), with its root `AGENTS.md`,
root `skills/`, and `.agents/skills -> ../skills`. An in-worktree root skills symlink
is supported, as in the bundle's seed layout. Other instruction locations, custom
subagents, plugins, duplicate skill names, nested skill symlinks, and unselected
skill sources are refused. The adapter inventories all advertised sources even
when skills or memory are disabled; absent directories are recorded as absent.
Installed dcode built-ins remain part of this Player.

Create a unique empty absolute profile outside the task worktree, then set these
variables **before the process imports dcode**:

```sh
export DEEPAGENTS_HOME=/tmp/my-unique-run/dcode-profile
export DEEPAGENTS_CODE_OFFLINE=1
export LANGSMITH_TRACING=false
export LANGCHAIN_TRACING_V2=false
export LANGCHAIN_TRACING=false
export GUARDKIT_PLAYER_EXPERIMENT='{"engine":"dcode","skills":["skills"],"memory":["AGENTS.md"],"dcode_home":"/tmp/my-unique-run/dcode-profile"}'
```

Do not change `HOME` or `CODEX_HOME`. A new independent run needs a new profile and
process; do not reload dcode modules. `DEEPAGENTS_HOME` does not hide home-level
`.agents/skills` or `.claude/skills`: an environment with unselected discovered
content fails clearly. The profile may contain only dcode's empty initial agent
instructions and empty directories. The adapter never prepares the project bundle.

For the planned comparison, use the proxy's `openai:workhorse` Player alias and
explicitly select its 131072-token context and 8192-token output limits. The
three-field form preserves the existing request behavior:

```sh
export GUARDKIT_PLAYER_MODEL_LIMITS='{"model":"openai:workhorse","context_tokens":131072,"output_tokens":8192}'
```

For a separately named thinking-off experiment, add the optional JSON boolean
`enable_thinking:false`:

```sh
export GUARDKIT_PLAYER_MODEL_LIMITS='{"model":"openai:workhorse","context_tokens":131072,"output_tokens":8192,"enable_thinking":false}'
```

Set the same carrier for all three comparison arms, independently of
`GUARDKIT_PLAYER_EXPERIMENT`. It applies only to LangGraph Player invocations;
other roles and the Claude SDK route ignore it, and absence retains the ordinary
model-resolution path. The JSON object requires the three limit fields and accepts
only that one optional field. Thinking-off requires the exact `openai:workhorse`
alias and the JSON boolean `false`; true, null, numbers, strings, duplicate keys,
unknown fields and other aliases are refused before model activity.

The resolved concrete `ChatOpenAI` sends
`chat_template_kwargs={"enable_thinking":false}` as a top-level Chat Completions
request field for main work, the inherited `general-purpose` subagent and
compaction. Conflicting reasoning, template or output controls are refused rather
than merged ambiguously. Unrelated existing `extra_body` entries are preserved.
An explicit local HTTP(S) `OPENAI_BASE_URL` remains required; credentials in the
URL, query strings, fragments and nonlocal hosts are refused. Dcode adds zero
graph/auxiliary retries; the existing provider retry budget and clients are
preserved. A shallow model copy holds dcode's retry metadata without changing the caller's model.

## Files, lifecycle and evidence

The factory backend remains the default for ordinary file operations and execution.
Only two filesystem-tool aliases receive extra routes:

| Tool alias | Physical directory in the canonical task worktree |
|---|---|
| `/conversation_history/` | `<task-worktree>/conversation_history/` |
| `/large_tool_results/` | `<task-worktree>/large_tool_results/` |

These aliases are not shell paths. Artifact directories must be real directories
inside the worktree; existing symlinks are rejected. Ordinary outside writes still
pass through the original confinement backend. Shell execution still requires the
authorized sandbox: the file wrapper does not confine arbitrary shell commands.
Keep independent acceptance files and hashes outside the Player's control.

The adapter omits `system_prompt`, preserving dcode's upstream headless coding
prompt, and supplies the task through the existing user message. It disables
questions, memory autosave and the optional interpreter. Automatic approval applies
to the authorized scratch workspace. Upstream built-ins include the general-purpose
subagent, compaction and an inactive goal tool; no goal/rubric state, MCP tools,
extensions, custom agents or separate summarization model are supplied.

Construction logs record source paths/hashes, absent sources, enabled tools,
sanitized model settings and artifact mappings. The returned graph also exposes
`guardkit_dcode_evidence` for diagnostics. Request evidence should record bodies and
routing without credentials. Discovery is checked before and after construction;
source or effective execution-directory mismatches fail before model activity.

The shared harness preserves callbacks, cancellation, generator cleanup and event
classes. Missing/empty final assistant text and length truncation raise
`LangGraphHarnessError` before any terminal success event. Successful events retain
the actual final message, finish reason and usage. Coach synthesis stays a bare
model request. `session_id=None` and `supports_resume=False` remain accurate.

## Verification

Run `tests/harness` in an ordinary Python 3.11 and Python 3.14 environment. In the
separate optional environment, launch a fresh profile and run:

```sh
python -m pytest -q tests/harness/test_player_experiment.py \
  tests/harness/test_player_skills_graph.py tests/harness/test_dcode_harness.py
```

The dcode cases use actual graph tools and fake HTTP, with socket denial and guarded
helper children. They cover selected reads, a syntax helper, a failing product test
followed by correction and the same test passing, inherited subagents, compaction,
large-result offload, truthful failures, provider errors/retries, cancellation and
consumer close. Set `DCODE_TEST_EVIDENCE` to a private directory to retain sanitized
requests and artifact/lifecycle evidence. Optional graph cases skip when the extra
or supported interpreter is absent; those skips do not establish enabled behavior.
