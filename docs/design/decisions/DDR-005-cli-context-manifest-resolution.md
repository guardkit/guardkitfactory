# DDR-005 — `.guardkit/context-manifest.yaml` resolution for GuardKit tool wrappers

## Status

Accepted

- **Date:** 2026-04-23
- **Session:** `/system-design`, design-pass 1
- **Related:** ADR-ARCH-004, refresh doc §"Context Manifest Convention"

---

## Context

Every GuardKit subcommand (11 of them — see ADR-ARCH-004) takes zero or more `--context <path>` flags pointing to markdown docs that seed the session. Previously these flags were assembled by hand inside Claude Desktop sessions and captured retrospectively in build plans. Forge needs to assemble them automatically when invoking `guardkit_*` tools.

The refresh doc §"Context Manifest Convention" established `.guardkit/context-manifest.yaml` at the target repo root as the discovery source:

```yaml
repo: forge
dependencies:
  nats-core:
    path: ../nats-core
    relationship: "Why this repo depends on nats-core"
    key_docs:
      - path: docs/design/specs/nats-core-system-spec.md
        category: specs
        description: "What this doc provides"
internal_docs:
  always_include:
    - docs/architecture/ARCHITECTURE.md
    - docs/design/DESIGN.md
```

Plus a filter-by-command-type rule (e.g. `/system-arch` wants architecture + decisions; `/feature-spec` wants specs + contracts + source).

Three open questions for Forge's wrapper layer:

1. **Where does the resolver live?** Inside `forge.adapters.guardkit` or as a separate library?
2. **What happens when a manifest is missing?** Fail the dispatch? Degrade silently?
3. **How are categories filtered per GuardKit command?** Hardcoded dict in Forge? Read from manifest? From GuardKit itself?

## Decision

**Placement.** The resolver lives in `forge.adapters.guardkit.context_resolver`. It's adapter-layer code (reads filesystem, composes CLI arguments) and has no domain concerns.

**Missing-manifest behaviour.** If `.guardkit/context-manifest.yaml` is absent, the resolver returns an empty context-flag list and logs a structured warning (`context_manifest_missing`). The GuardKit invocation proceeds without `--context` flags. The reasoning model sees the warning in the tool's return JSON and decides whether to retry with explicit flags or HARD_STOP.

**Category filter table.** Hardcoded in `forge.adapters.guardkit.context_resolver` — a single dict keyed by GuardKit subcommand name mapping to allowed categories:

```python
_COMMAND_CATEGORY_FILTER: dict[str, set[str]] = {
    "system-arch":    {"architecture", "decisions"},
    "system-design":  {"specs", "decisions", "contracts", "architecture"},
    "system-plan":    {"architecture", "decisions", "specs"},
    "feature-spec":   {"specs", "contracts", "source", "decisions"},
    "feature-plan":   {"specs", "decisions", "architecture"},
    "task-review":    {"contracts", "source"},
    "task-work":      {"contracts", "source"},
    "task-complete":  {"contracts", "source"},
    "autobuild":      {"contracts", "source"},
    # GuardKit graphiti subcommands don't take --context; skip resolution entirely.
}
# Always-included docs (manifest.internal_docs.always_include) prepend regardless of filter.
```

**Circular dependency guard.** The resolver detects cycles when chasing `dependencies` recursively and stops at depth 2 with a warning (`context_manifest_cycle_detected`).

**Path resolution.** All paths are resolved relative to the target repo root, then converted to absolute paths before being passed to GuardKit. Symlinks are followed; paths outside the repo's allowed-read list (`forge.yaml.permissions.filesystem.read_allowlist`) are omitted with a warning.

## Rationale

- **Adapter-layer placement** — the resolver touches the filesystem and composes shell arguments; neither is a domain concern. Co-locating with `forge.adapters.guardkit.run` keeps the call path short.
- **Missing-manifest degrades gracefully** — Forge should be able to drive repos that don't yet have a manifest; forcing one as a hard precondition would block early adoption.
- **Hardcoded filter table in Forge** — the mapping is stable and belongs with the caller; pushing it into the manifest would require every repo to restate the same rules, and pushing it into GuardKit couples GuardKit to category vocabulary it doesn't care about.
- **Depth-2 cycle guard** — realistic dependency graphs are narrow (e.g. forge → nats-core → ∅). If Rich later needs deeper, this DDR can be superseded.

## Alternatives considered

- **Fail-hard on missing manifest** — rejected; blocks early adoption.
- **Per-repo filter override in `context-manifest.yaml`** — rejected; adds configurability that will rarely be used and duplicates the stable rule across repos.
- **Ask GuardKit for category hints** — rejected; unnecessary coupling.
- **Depth-unlimited cycle traversal** — rejected; no realistic benefit, high risk of O(n²) traversal on bad manifests.

## Consequences

- **+** GuardKit invocations are deterministic from manifest + subcommand — no hand-assembly.
- **+** Repos without manifests still work; Forge emits a structured warning into the reasoning loop instead of failing.
- **+** Filter logic is local and testable.
- **−** Hardcoded filter table requires editing Forge source when a new GuardKit subcommand appears. Manageable — new subcommands come with a new `@tool` anyway (ADR-ARCH-004 pattern).
- **−** Depth-2 cycle cap may feel restrictive; easy to revisit via a follow-up DDR.

## Related components

- GuardKit Adapter (`forge.adapters.guardkit`)
- Tool Layer (`guardkit_*` tools — [API-tool-layer.md §6](../contracts/API-tool-layer.md#6-guardkit-subcommand-tools))
- Subprocess contract — [API-subprocess.md §3.3](../contracts/API-subprocess.md#33-context-manifest-resolution)
