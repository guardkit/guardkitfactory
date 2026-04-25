# FEAT-FORGE-005 — GuardKit Command Invocation Engine

The subprocess surface Forge uses to drive every GuardKit subcommand
(`/system-arch`, `/system-design`, `/system-plan`, `/feature-spec`,
`/feature-plan`, `/task-review`, `/task-work`, `/task-complete`, `autobuild`,
plus the Graphiti subcommands) and the git/gh adapter that brackets a build.

## Status

| Field | Value |
|---|---|
| Feature ID | FEAT-FORGE-005 |
| Review | TASK-REV-GCI0 |
| Spec | `features/guardkit-command-invocation-engine/guardkit-command-invocation-engine.feature` (32 scenarios) |
| Build plan | `docs/research/ideas/forge-build-plan.md` Wave 2 |
| Depends on | FEAT-FORGE-001 (`forge.yaml`, worktrees, state machine) |
| Parallel-safe with | FEAT-FORGE-002 (NATS Fleet Integration) |
| Estimated effort | 2–3 days |
| Aggregate complexity | 6 (medium) |
| Tasks | 11 |
| Waves | 5 |

## Tasks

| Wave | ID | Title | Mode | Compl. |
|---|---|---|---|---|
| 1 | TASK-GCI-001 | Define GuardKitResult and result Pydantic models | direct | 3 |
| 1 | TASK-GCI-002 | Define GitOpResult, PRResult, progress event DTOs | direct | 3 |
| 2 | TASK-GCI-003 | Implement context_resolver.resolve_context_flags() (DDR-005) | task-work | 6 |
| 2 | TASK-GCI-004 | Implement parse_guardkit_output() tolerant parser | task-work | 5 |
| 2 | TASK-GCI-005 | Implement NATS progress-stream subscriber (telemetry) | task-work | 5 |
| 2 | TASK-GCI-006 | Implement forge.adapters.git (worktree/commit/push/cleanup) | task-work | 5 |
| 2 | TASK-GCI-007 | Implement forge.adapters.gh (create_pr, missing-cred error) | task-work | 4 |
| 3 | TASK-GCI-008 | Implement forge.adapters.guardkit.run() subprocess wrapper | task-work | 7 |
| 4 | TASK-GCI-009 | Wire 9 guardkit_* @tool wrappers (system/feature/task/autobuild) | task-work | 6 |
| 4 | TASK-GCI-010 | Wire 2 Graphiti guardkit_* @tool wrappers (bypass resolver) | task-work | 4 |
| 5 | TASK-GCI-011 | BDD scenario pytest wiring (R2 oracle activation) | task-work | 5 |

## Quickstart

Implementation-guide diagrams + per-wave plan: see
[IMPLEMENTATION-GUIDE.md](IMPLEMENTATION-GUIDE.md).

```bash
# Wave 1 (parallel, ~30 min each)
guardkit task-work TASK-GCI-001
guardkit task-work TASK-GCI-002

# Wave 2 (5 parallel tasks — Conductor recommended)
guardkit task-work TASK-GCI-003   # context_resolver
guardkit task-work TASK-GCI-004   # parser
guardkit task-work TASK-GCI-005   # progress subscriber
guardkit task-work TASK-GCI-006   # git adapter
guardkit task-work TASK-GCI-007   # gh adapter

# Wave 3 (joins resolver+parser)
guardkit task-work TASK-GCI-008   # run() subprocess wrapper

# Wave 4 (parallel)
guardkit task-work TASK-GCI-009   # 9 guardkit_* @tool wrappers
guardkit task-work TASK-GCI-010   # 2 Graphiti @tool wrappers

# Wave 5
guardkit task-work TASK-GCI-011   # BDD pytest wiring
```

Or:

```bash
guardkit feature-build FEAT-FORGE-005   # autobuild end-to-end
```

## Cross-cutting invariants

Every task must respect:

1. **Universal error contract (ADR-ARCH-025)** — adapters and tools wrap
   their bodies in `try/except` and return structured failures / error
   strings; cancellation propagates, nothing else does.
2. **Worktree confinement (ADR-ARCH-028)** — every subprocess runs with
   `cwd` inside the build worktree allowlist.
3. **Constitutional permissions (ADR-ARCH-023)** — `forge.yaml.permissions`
   is not reasoning-adjustable; the adapter layer relies on DeepAgents
   enforcement.
4. **Stateless resolver and runner (ASSUM-007)** — no module-level caches.
5. **Tolerant parsing** — unknown GuardKit output shapes degrade to
   success-with-no-artefacts, never raise.
6. **Telemetry is non-authoritative** — missing/slow progress stream must
   not affect the synchronous result.

## References

- API contract (tool layer): `docs/design/contracts/API-tool-layer.md` §6, §2
- API contract (subprocess): `docs/design/contracts/API-subprocess.md` §1–6
- Design decision: `docs/design/decisions/DDR-005-cli-context-manifest-resolution.md`
- Build plan: `docs/research/ideas/forge-build-plan.md` FEAT-FORGE-005 row
- Feature spec: `features/guardkit-command-invocation-engine/guardkit-command-invocation-engine.feature`
- Assumptions: `features/guardkit-command-invocation-engine/guardkit-command-invocation-engine_assumptions.yaml`
- Review task: `tasks/backlog/TASK-REV-GCI0-plan-guardkit-command-invocation-engine.md`
