# Coding skills bundle

This directory is a standalone set of starting instructions and two coding
skills. It is intended to be supplied unchanged to the native Deep Agents SDK
worker and to dcode in a later, explicit integration. Nothing in this example
wires the bundle into guardkitfactory, selects it at runtime, or proves that a
worker loaded it. Factory integration remains blocked until its separate SDK
foundation has an accepted review.

## Contents

- `AGENTS.md`: concise repository-level coding instructions.
- `skills/planning/SKILL.md`: a tool-neutral planning workflow.
- `skills/code-review/SKILL.md`: a review workflow and the syntax-check command.
- `skills/code-review/lint_check.py`: a standard-library-only Python syntax
  checker with a root boundary.
- `tests/test_lint_check.py`: isolated command-line behavior tests for the
  helper.
- `LICENSE`: the upstream MIT license retained for the adapted material.

## Deploy and use

Copy this whole directory into the isolated workspace used for a run. Configure
that runtime explicitly, later, to use `skills/` as a skill source and
`AGENTS.md` as an instruction source. Keep both comparison arms pointed at the
same copied bytes. Do not describe the bundle as active until the runtime has
reported the selected sources and an integration check has observed the files
being read.

Deep Agents 0.7.14 accepts explicit skill source paths through
`create_deep_agent(..., skills=[...])`; the paths are interpreted through the
configured backend. This is a description of the pinned SDK interface, not
runtime wiring in this repository. dcode configuration will be specified and
verified by its separate integration.

Run the helper only when Python execution is available:

```bash
python skills/code-review/lint_check.py --root . path/to/one.py path/to/two.py
```

File arguments may be absolute or relative to `--root`. The helper resolves
every argument, checks every valid in-root regular `.py` file in sorted order,
and exits nonzero if any input is invalid, unreadable, incorrectly encoded, or
syntactically invalid. It parses source and never imports or executes the code
being checked. A successful syntax check is not a substitute for the product's
actual tests.

The bundle makes no cross-run memory claim. In particular, whether a saved
`AGENTS.md` correction is visible to a newly constructed graph remains deferred
until the actual graph and isolated storage configuration are verified.

## Provenance

The planning and code-review examples were adapted from `langchain-ai/deepagents`
at commit `1d3232c0852c47af09119edea10eeec887e4f0da`:

| Bundle file | Upstream path | Upstream SHA-256 | Treatment |
|---|---|---|---|
| `skills/planning/SKILL.md` | `examples/deploy-coding-agent/skills/planning/SKILL.md` | `5733ac8765d86d4c8d7de12e816eb85572e53400d2aa0bb5a310b22781685fac` | Adapted to avoid assuming a todo tool and to require evidence-based planning. |
| `skills/code-review/SKILL.md` | `examples/deploy-coding-agent/skills/code-review/SKILL.md` | `39271a17e19d04642e70d8aac0ede76717bc20c64c8e284dcf37833c984961f6` | Adapted to avoid assuming command names and to use the bounded syntax helper. |
| `skills/code-review/lint_check.py` | `examples/deploy-coding-agent/skills/code-review/lint_check.py` | `c52727fa3c3058e6d32f73a7d8ef1433c174212a95d4c0d9ec892430d9f4ae45` | Adapted into a fail-closed syntax checker with explicit file inputs and root containment. |
| `LICENSE` | `LICENSE` | `4ec67e4ca6e6721dba849b2ca82261597c86a61ee214bbf21416006b7b2d0478` | Copied byte-for-byte. |

`README.md`, `AGENTS.md`, and `tests/test_lint_check.py` are new for this
bundle. SDK statements above were checked against the official
`deepagents-0.7.14` source distribution (SHA-256
`69b3050e3e0a1998d07d62cf70cc7c675e7674f7671a5b869fd113b9988493a9`).
