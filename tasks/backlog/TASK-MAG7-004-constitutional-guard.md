---
id: TASK-MAG7-004
title: Implement ConstitutionalGuard for PR-review enforcement
task_type: feature
status: backlog
priority: high
created: 2026-04-25T00:00:00Z
updated: 2026-04-25T00:00:00Z
parent_review: TASK-REV-MAG7
feature_id: FEAT-FORGE-007
wave: 2
implementation_mode: task-work
complexity: 4
dependencies: [TASK-MAG7-001]
tags: [guard, constitutional, security, belt-and-braces, feat-forge-007]
consumer_context:
  - task: TASK-MAG7-001
    consumes: stage_taxonomy
    framework: "Python forge.pipeline.stage_taxonomy"
    driver: "StrEnum"
    format_note: "Imports StageClass and CONSTITUTIONAL_STAGES from forge.pipeline.stage_taxonomy"
test_results:
  status: pending
  coverage: null
  last_run: null
---

# Task: Implement ConstitutionalGuard for PR-review enforcement

## Description

Pure-function guard that enforces the ADR-ARCH-026 belt-and-braces rule for
constitutional stages: pull-request review must always resolve under mandatory
human approval. Refuses auto-approve directives, refuses skip directives, and
refuses any specialist override claim — at the executor layer, independent of
prompt content.

Covers FEAT-FORGE-007 Group C (auto-approve refused, skip refused) and
Group E (security: holds against misconfigured prompt; specialist override
ignored).

## Acceptance Criteria

- [ ] `ConstitutionalGuard` class exists at
      `src/forge/pipeline/constitutional_guard.py`
- [ ] Method `veto_auto_approve(stage: StageClass) -> AutoApproveDecision`
      returns `REFUSED` for any stage in `CONSTITUTIONAL_STAGES`,
      regardless of upstream Coach score
- [ ] Method `veto_skip(stage: StageClass) -> SkipDecision`
      returns `REFUSED_CONSTITUTIONAL` for any stage in
      `CONSTITUTIONAL_STAGES`
- [ ] Method `veto_override_claim(stage: StageClass, claim: dict) -> bool`
      returns True (ignore-the-claim) when stage is constitutional, even if
      the claim asserts authority
- [ ] Returns include a structured rationale string suitable for recording in
      `stage_log.gate_rationale`
- [ ] Unit tests cover Group C @negative @regression scenarios:
      max-Coach-score does not bypass; skip directive refused
- [ ] Unit tests cover Group E @security @regression scenarios:
      misconfigured-prompt scenario, specialist-override claim
- [ ] Pure function — no I/O, no async
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Implementation Notes

This is the executor-layer half of ADR-ARCH-026. The prompt-layer half lives
in the supervisor's GUARDRAILS section (out of scope for this task — it's
already wired in FEAT-FORGE-004's PR-review constitutional rule).

Loss of either layer is a constitutional regression. The Group E security
test deliberately misconfigures the prompt and asserts that this guard still
refuses — that is the canary for the belt-and-braces invariant.

Reference: ADR-ARCH-026 (Constitutional Rules at Two Layers),
FEAT-FORGE-004 ASSUM-004 (constitutional override target identifiers).

## Seam Tests

```python
"""Seam test: verify ConstitutionalGuard refuses auto-approve at PR-review."""
import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("constitutional_pr_review_rule")
def test_constitutional_guard_refuses_pr_auto_approve():
    """Verify executor-layer refusal of auto-approve at PR-review.

    Contract: ADR-ARCH-026 belt-and-braces; PR-review never auto-approves.
    Producer: TASK-MAG7-001 (CONSTITUTIONAL_STAGES set)
    """
    from forge.pipeline.constitutional_guard import ConstitutionalGuard
    from forge.pipeline.stage_taxonomy import StageClass

    guard = ConstitutionalGuard()
    decision = guard.veto_auto_approve(StageClass.PULL_REQUEST_REVIEW)
    assert decision.is_refused, "PR-review must never auto-approve"
```

## Test Execution Log

[Automatically populated by /task-work]
