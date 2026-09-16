---
name: planning
description: Break down a coding task into a concrete implementation and verification plan grounded in the repository.
license: MIT
---

# Planning

Use this skill before a coding task with several dependent changes, meaningful
risk, or unclear repository seams. For a small, obvious edit, a written plan may
add no value.

## Build the plan

1. Read the complete request and record the observable outcome, acceptance
   checks, constraints, allowed paths, and prohibited actions.
2. Find the repository root and read its instructions, project overview, and
   relevant test guidance.
3. Inspect the current implementation, its callers, and representative tests.
   Search for the exact symbols and behavior involved rather than guessing from
   filenames.
4. Separate facts found in the repository from assumptions. Resolve assumptions
   that affect the design; surface a missing user decision only when it would
   materially change the result.
5. Write three to ten ordered steps. Name the concrete files or seams, the
   behavior each step changes, and the evidence that will show it works.
6. Include relevant failure cases, regression checks, complete-diff review, and
   final path-scope verification.

Keep the plan in the response or use a planning tool only if the runtime exposes
one. Do not assume `write_todos`, a researcher, a subagent, or any other command
exists. Update the plan when evidence changes it, and reconcile every item before
finishing.

## Plan quality

- Make each step executable without another round of planning.
- Reuse established repository patterns unless the task requires changing them.
- Keep implementation and verification separate enough that failures are clear.
- Match verification effort to risk. Syntax checks do not replace product tests.
- Do not claim a source was read, a command ran, or a result passed without
  direct evidence.

Adapted from `examples/deploy-coding-agent/skills/planning/SKILL.md` at
`langchain-ai/deepagents@1d3232c0852c47af09119edea10eeec887e4f0da`.
