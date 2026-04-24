# Autobuild Review Summary: FEAT-FORGE-002

**Status:** FAILED  
**Generated:** 2026-04-24 12:35 UTC

## Metrics

| Metric | Value |
|--------|-------|
| Total tasks | 11 |
| Total turns | 6 |
| Avg turns/task | 3.00 |
| Waves executed | 1 |
| First-attempt pass rate | 0% |

## Per-Task Outcomes

| Task | Wave | Turns | Outcome | Decision | Notes |
|------|------|-------|---------|----------|-------|
| TASK-NFI-001 | 1 | 3 | FAILED | unrecoverable_stall | Unrecoverable stall detected after 3 turn(s). AutoBuild cannot make forward progress. |
| TASK-NFI-002 | 1 | 3 | FAILED | unrecoverable_stall | Unrecoverable stall detected after 3 turn(s). AutoBuild cannot make forward progress. |

## Quality Metrics

- Task success rate: 0%
- First-turn approvals: 0/2
- SDK ceiling hits: 0

## Turn Efficiency

| Metric | Value |
|--------|-------|
| Avg turns/task | 3.0 |
| Single-turn tasks | 0 |
| Multi-turn tasks | 2 |
| Avg SDK turns/invocation | 0.0 |

## Key Findings

- Tasks required multiple turns before failing: TASK-NFI-001, TASK-NFI-002. Review coach feedback logs for recurring patterns.
- State recovery used: TASK-NFI-001 (3x), TASK-NFI-002 (3x).
