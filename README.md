# guardkitfactory

LangGraph-based harness for the [GuardKit](https://github.com/guardkit/guardkit)
AutoBuild adversarial-cooperation orchestrator.

This repository is the **harness substrate** for GuardKit AutoBuild: the
LangGraph-backed Player/Coach execution harness, the backend/model/permissions
configuration that adapts it to different model substrates (Anthropic,
OpenAI-compatible / llama-swap on the GB10), the BDD contract surface the Coach
consumes, and the deterministic wiring/seam analyzer that catches cross-repo
composition drift. It began life as the `langchain-deepagents` template
scaffold (parent review **TASK-REV-HMIG**, feature **FEAT-HMIG**); that
migration is now complete and the package is published as **v0.2.0** — the
first tagged release, consumed by `guardkit` against a pinned version contract.

## Status

The harness migration (FEAT-HMIG) is complete; the wiring/seam layer
(WS3-S3) landed on top of it. What ships today:

| Area | Module | State |
|---|---|---|
| LangGraph harness | `guardkitfactory.harness.LangGraphHarness` | shipped — concrete `HarnessAdapter` subclass (TASK-HMIG-001B) |
| Backend / model / permissions config | `guardkitfactory.harness` (`build_autobuild_backend`, `resolve_autobuild_model`, `build_autobuild_permissions`) | shipped (TASK-HMIG-002R) |
| BDD contract surface | `guardkitfactory.bdd` (`discover`, `BDDRunResult`, `StackProfile`, `Scenario`, `BDDPlugin`) | shipped — the seam the Coach BDD bridge binds to |
| Wiring / seam analyzer | `guardkitfactory.wiring` (`analyze_wiring`, CALLSITE_DRIFT, SYS_MODULES_TAMPER / env-tamper, PERMISSIVE_DOUBLE, stub-scan) | shipped (WS3-S3) |
| Vendored template helpers | `guardkitfactory.lib` (factory guards, JSON extraction, retry context, session logging) | shipped |

`HarnessAdapter` (the top-level symbol) is a retained **placeholder** that
raises `NotImplementedError`; it exists only for the original TASK-HMIG-000R
smoke-test contract. Use `guardkitfactory.LangGraphHarness` for the concrete
harness, or `guardkit.orchestrator.harness.HarnessAdapter` for the ABC it
subclasses.

## Bootstrap

This project pins per the [GuardKit portfolio Python pinning standard][pps] —
`requires-python = ">=3.11"` with no closed upper bound. Defensive upper
bounds belong in CI matrices, not in `requires-python`; the rationale and
the stall incident this protects against are in the linked guide.

[pps]: https://github.com/guardkit/guardkit/blob/main/docs/guides/portfolio-python-pinning.md

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip 23+

```bash
git clone https://github.com/guardkit/guardkitfactory.git
cd guardkitfactory

# uv (recommended)
uv sync --extra dev
uv run pytest tests/

# Or with plain pip
pip install -e ".[dev]"
pytest tests/
```

Smoke check that the package imports and exposes its public API:

```bash
python -c 'import guardkitfactory; print(guardkitfactory.__version__)'
python -c 'from guardkitfactory import LangGraphHarness, discover; print(LangGraphHarness, discover)'
```

## Layout

```
guardkitfactory/
├── pyproject.toml            # version 0.2.0; deepagents>=0.6.7,<1, langgraph>=1,<2,
│                             #   langchain>=1.2,<2, langchain-core>=1.2,<2,
│                             #   langchain-openai>=1,<2, tree-sitter>=0.25,<1
├── src/guardkitfactory/      # the installable package (src layout)
│   ├── __init__.py           # public API re-exports + placeholder HarnessAdapter
│   ├── harness/              # LangGraphHarness + backend/model/permissions config
│   ├── bdd/                  # BDD discovery + run-result contract (Coach bridge seam)
│   ├── wiring/               # deterministic wiring/seam analyzer (WS3-S3)
│   └── lib/                  # vendored helpers from the langchain-deepagents template
│       ├── factory_guards.py     # tool allowlisting + ainvoke() guard (TASK-REV-R2A1)
│       ├── json_extractor.py     # 5-strategy JSON extraction cascade
│       ├── retry_context.py      # retry-input + context manifest (Category C fix)
│       └── session_logging.py    # per-run diagnostic JSON + logging bootstrap (Category A fix)
├── tests/                    # 300+ tests: harness/, bdd/, wiring/, test_smoke.py
└── .github/workflows/ci.yml
```

The helpers ship **inside** the package namespace as
`guardkitfactory.lib`, so `from guardkitfactory.lib.factory_guards import …`
works after a `pip install -e .`. They used to ship as a bare top-level `lib`
distribution package; in the forge image that shadowed guardkit's own
`installer/core/lib` and broke its fix-task producer
(`from lib.review_parser import …` → `ModuleNotFoundError`). See instance #3 in
guardkit's `.claude/rules/namespace-hygiene.md` — this distribution must never
ship a bare top-level package again.

## Cross-repo dependency

`guardkitfactory` is consumed by GuardKit's AutoBuild orchestrator. It is not
published to PyPI; guardkit resolves it **operator-side as an editable sibling
checkout** via `[tool.uv.sources]`, pinned to the published version contract
(`guardkitfactory>=0.2.0,<1`):

```bash
# Sibling checkouts
~/Projects/appmilla_github/guardkit          # AutoBuild orchestrator
~/Projects/appmilla_github/guardkitfactory   # this repo

# guardkit resolves ../guardkitfactory editable via [tool.uv.sources];
# `uv sync --extra autobuild` (or pip install -e ../guardkitfactory) wires it.
cd ~/Projects/appmilla_github/guardkit
uv sync --extra autobuild
```

Editable means changes here are picked up by `from guardkitfactory import
LangGraphHarness` in guardkit without a reinstall. The version contract
(`>=0.2.0`) names the published release as the floor; the tag **v0.2.0** marks
the exact commit the sibling checkout tracks.

### Seam drift guard

The guardkit↔guardkitfactory contract boundary is CI-gated by
`guardkit/.github/workflows/seam-tests.yml` ("Seam Tests (harness contract)").
It checks out this repo, installs it editable, and runs the `@pytest.mark.seam`
cross-repo contract tests against the **real** installed guardkitfactory — not
mocks — on every guardkit PR/push. It catches signature/field drift across the
harness, BDD, and wiring seams in seconds, the class of drift that previously
cost a full autobuild run to discover. The seam job tracks guardkitfactory's
default branch (not a pinned tag) so it detects drift as it lands.

## Develop alongside guardkit

If you are working the harness or seam layers you'll typically want both repos
open:

1. **Branch in lock-step** — keep `guardkit` and `guardkitfactory` on
   matching feature branches when a change touches both sides of the seam.
2. **Editable install** — see the snippet above. The `guardkit` orchestrator
   imports `guardkitfactory` at autobuild dispatch time; an editable
   install means iterative changes don't require a reinstall.
3. **CI** — this repo's `ci.yml` runs in isolation (it does not depend on
   `guardkit`). The cross-repo contract is exercised by guardkit's
   `seam-tests.yml` (see above).
4. **Migrations** — task files under `tasks/` and migration notes under
   `migrations/` are committed *here*, not in `guardkit`, because the
   harness *is* the migration.

## Pin rationale

| Pin | Why |
|---|---|
| `deepagents>=0.6.7,<1` | Floor bumped from 0.5 for grep/read_file/state-schema stability fixes AutoBuild depends on (see the `pyproject.toml` comment for the per-patch changelog); `<1` is a soft guard against a 1.0 API shift. |
| `langgraph>=1,<2`    | The harness targets the LangGraph 1.x API surface. |
| `langchain>=1.2,<2`  | Matches the LangChain `1.2` line `create_agent()` lives in. |
| `langchain-core>=1.2,<2` | Pinned in lock-step with `langchain` to avoid resolver drift. |
| `langchain-openai>=1,<2` | Required at runtime for the OpenAI-compatible / llama-swap substrate (TASK-OPS-COACHMOE01); imported lazily but must be installed. |
| `tree-sitter>=0.25,<1` + `tree-sitter-language-pack>=1.0,<2` | Stack-agnostic parsing for the wiring analyzer; the pack ships precompiled python/js/ts/csharp grammars. |
| `requires-python = ">=3.11"` | Portfolio canonical (no closed upper bound) — see [`portfolio-python-pinning.md`][pps]. |

## References

- Parent review: **TASK-REV-HMIG** — the autobuild harness migration
  (lives in the `guardkit` repo).
- Pinning standard: [`portfolio-python-pinning.md`][pps] in `guardkit`.
- Template source: `guardkit/installer/core/templates/langchain-deepagents/`
  — the `guardkitfactory.lib` helpers vendored here are derived directly from it.

## License

MIT — see [LICENSE](LICENSE).
