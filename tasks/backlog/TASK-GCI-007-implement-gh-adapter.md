---
id: TASK-GCI-007
title: Implement forge.adapters.gh (create_pr, missing-credential error)
task_type: feature
status: blocked
priority: high
created: 2026-04-25 00:00:00+00:00
updated: 2026-04-25 00:00:00+00:00
parent_review: TASK-REV-GCI0
feature_id: FEAT-FORGE-005
wave: 2
implementation_mode: task-work
complexity: 4
dependencies:
- TASK-GCI-002
tags:
- gh
- github
- adapter
- pull-request
- subprocess
test_results:
  status: pending
  coverage: null
  last_run: null
autobuild_state:
  current_turn: 3
  max_turns: 30
  worktree_path: /home/richardwoollcott/Projects/appmilla_github/forge/.guardkit/worktrees/FEAT-FORGE-005
  base_branch: main
  started_at: '2026-04-26T08:37:22.097514'
  last_updated: '2026-04-26T08:37:29.161370'
  turns:
  - turn: 1
    decision: feedback
    feedback: "- Advisory (non-blocking): task-work produced a report with 0 of 3\
      \ expected agent invocations. Missing phases: 3 (Implementation), 4 (Testing),\
      \ 5 (Code Review). Consider invoking these agents via the Task tool to strengthen\
      \ stack-specific quality:\n- Phase 3: `python-api-specialist` (Implementation)\n\
      - Phase 4: `test-orchestrator` (Testing)\n- Phase 5: `code-reviewer` (Code Review)\n\
      - Independent test verification failed:\n  SDK API error: authentication_failed\n\
      \n[Command Execution Advisory]\n- Command `gh pr create --title <t> --body <b>\
      \ --base <base>` failed (unknown (may be implementation-related)):\n  /bin/sh:\
      \ 1: Syntax error: end of file unexpected"
    timestamp: '2026-04-26T08:37:22.097514'
    player_summary: '[RECOVERED via player_report] Original error: SDK agent error:
      authentication_failed'
    player_success: true
    coach_success: true
  - turn: 2
    decision: feedback
    feedback: "- Advisory (non-blocking): task-work produced a report with 0 of 3\
      \ expected agent invocations. Missing phases: 3 (Implementation), 4 (Testing),\
      \ 5 (Code Review). Consider invoking these agents via the Task tool to strengthen\
      \ stack-specific quality:\n- Phase 3: `python-api-specialist` (Implementation)\n\
      - Phase 4: `test-orchestrator` (Testing)\n- Phase 5: `code-reviewer` (Code Review)\n\
      - Independent test verification failed:\n  SDK API error: authentication_failed\n\
      \n[Command Execution Advisory]\n- Command `gh pr create --title <t> --body <b>\
      \ --base <base>` failed (unknown (may be implementation-related)):\n  /bin/sh:\
      \ 1: Syntax error: end of file unexpected"
    timestamp: '2026-04-26T08:37:26.140473'
    player_summary: '[RECOVERED via player_report] Original error: SDK agent error:
      authentication_failed'
    player_success: true
    coach_success: true
  - turn: 3
    decision: feedback
    feedback: "- Advisory (non-blocking): task-work produced a report with 0 of 3\
      \ expected agent invocations. Missing phases: 3 (Implementation), 4 (Testing),\
      \ 5 (Code Review). Consider invoking these agents via the Task tool to strengthen\
      \ stack-specific quality:\n- Phase 3: `python-api-specialist` (Implementation)\n\
      - Phase 4: `test-orchestrator` (Testing)\n- Phase 5: `code-reviewer` (Code Review)\n\
      - Independent test verification failed:\n  SDK API error: authentication_failed\n\
      \n[Command Execution Advisory]\n- Command `gh pr create --title <t> --body <b>\
      \ --base <base>` failed (unknown (may be implementation-related)):\n  /bin/sh:\
      \ 1: Syntax error: end of file unexpected"
    timestamp: '2026-04-26T08:37:27.696730'
    player_summary: '[RECOVERED via git_only] Original error: SDK agent error: authentication_failed'
    player_success: true
    coach_success: true
---

# Task: Implement forge.adapters.gh (create_pr, missing-credential error)

## Description

Build the thin wrapper over DeepAgents `execute` for `gh pr create`. Returns
`PRResult` (TASK-GCI-002) and converts a missing `GH_TOKEN` env var into a
structured error rather than letting `gh` exit with a confusing prompt
(Scenario "A pull-request creation without GitHub credentials returns a
structured error").

Per `docs/design/contracts/API-subprocess.md` §4 + §4.1 (gh authentication).

## Implementation

```python
# src/forge/adapters/gh/operations.py
import os
from pathlib import Path
from forge.adapters.git.models import PRResult


async def create_pr(
    worktree: Path,
    title: str,
    body: str,
    base: str = "main",
    draft: bool = False,
) -> PRResult: ...
```

## Acceptance Criteria

- [ ] `create_pr()` in `src/forge/adapters/gh/operations.py`, returning
      `PRResult`
- [ ] Pre-flight check: if `GH_TOKEN` is unset (or empty) in `os.environ`,
      return `PRResult(status="failed", error_code="missing_credentials",
      stderr="GH_TOKEN not set in environment")` **without invoking gh**
      (Scenario "A pull-request creation without GitHub credentials returns
      a structured error")
- [ ] Otherwise, invoke `gh pr create --title <t> --body <b> --base <base>`
      (plus `--draft` if requested) via DeepAgents `execute` with `cwd =
      worktree`
- [ ] On success, parse the PR URL from gh's stdout and populate
      `PRResult.pr_url` and `PRResult.pr_number` (parsed from the trailing
      slash component of the URL)
- [ ] On non-zero exit, `PRResult(status="failed", stderr=...)`, no
      exception
- [ ] Function body wrapped in `try/except Exception as exc:` returning a
      `failed` `PRResult` — never raises (ADR-ARCH-025)
- [ ] Arguments containing shell metacharacters (e.g. backticks in PR body)
      are passed as separate list tokens to `execute`, never via
      shell-string concatenation (Scenario "Shell metacharacters in
      subprocess arguments are passed as literal tokens")
- [ ] Unit tests: missing GH_TOKEN, success path with parsed URL, non-zero
      exit, raised exception, body containing backticks/dollar-signs
- [ ] All modified files pass project-configured lint/format checks with zero
      errors

## Implementation Notes

- Do **not** read `GH_TOKEN` once at import time — re-check on every call
  (the env may legitimately change between builds in a long-running
  process)
- gh's PR-URL line is typically the last non-empty line of stdout, e.g.
  `https://github.com/owner/repo/pull/123`. Use a small regex
  (`r"https://github\.com/[^/]+/[^/]+/pull/(\d+)"`) over `stdout.strip()`
  rather than splitting by newlines
- Do not handle credential-store interactions; per API-subprocess.md §4.1,
  Forge does not manage GitHub credentials — `GH_TOKEN` is sourced from the
  env by Docker deployment

## Seam Tests

`@pytest.mark.seam` integration tests should mock `execute` rather than call
the real `gh` binary (avoids network + auth dependencies in CI). Validate
the missing-credential branch returns `error_code="missing_credentials"`
without ever invoking `execute`. Tag with
`@pytest.mark.integration_contract("gh_adapter_subprocess_contract")`.
