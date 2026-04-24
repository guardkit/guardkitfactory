# Autobuild Review Summary: FEAT-FORGE-002

**Status:** FAILED  
**Generated:** 2026-04-24 18:26 UTC

## Metrics

| Metric | Value |
|--------|-------|
| Total tasks | 11 |
| Total turns | 9 |
| Avg turns/task | 1.80 |
| Waves executed | 2 |
| First-attempt pass rate | 60% |

## Per-Task Outcomes

| Task | Wave | Turns | Outcome | Decision | Notes |
|------|------|-------|---------|----------|-------|
| TASK-NFI-001 | 1 | 1 | PASSED | approved |  |
| TASK-NFI-002 | 1 | 1 | PASSED | approved |  |
| TASK-NFI-003 | 2 | 3 | FAILED | unrecoverable_stall | coach_agent_invocations_stall + context_pollution_stall_no_checkpoint | Unrecoverable stall detected after 3 turn(s). AutoBuild cannot make forward progress. |
| TASK-NFI-006 | 2 | 1 | PASSED | approved |  |
| TASK-NFI-007 | 2 | 3 | FAILED | unrecoverable_stall | coach_agent_invocations_stall + context_pollution_stall_no_checkpoint | Unrecoverable stall detected after 3 turn(s). AutoBuild cannot make forward progress. |

## Quality Metrics

- Task success rate: 60%
- First-turn approvals: 3/5
- SDK ceiling hits: 0

## Turn Efficiency

| Metric | Value |
|--------|-------|
| Avg turns/task | 1.8 |
| Single-turn tasks | 3 |
| Multi-turn tasks | 2 |
| Avg SDK turns/invocation | 28.3 |

## Key Findings

- Tasks required multiple turns before failing: TASK-NFI-003, TASK-NFI-007. Review coach feedback logs for recurring patterns.
