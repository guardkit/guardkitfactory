# guardkitfactory

LangGraph-based harness for the [GuardKit](https://github.com/appmilla/guardkit)
AutoBuild adversarial-cooperation orchestrator.

This repository is the substrate of the autobuild harness migration
(parent review **TASK-REV-HMIG**, feature **FEAT-HMIG**). At this stage it
provides only the **scaffold** — `pyproject.toml`, package layout, vendored
helpers from the `langchain-deepagents` template, and CI. The real
`LangGraphHarness` and pluggable-backend configuration land in follow-up
tasks (`TASK-HMIG-001B`, `TASK-HMIG-002R`).

## Status

| Task | Description | Status |
|---|---|---|
| TASK-HMIG-000R | Source scaffold (this commit) | in-review |
| TASK-HMIG-001B | `LangGraphHarness` implementation | pending |
| TASK-HMIG-002R | Pluggable backend configuration | pending |
| TASK-HMIG-007  | Player/Coach wiring                | pending |

## Bootstrap

This project pins per the [GuardKit portfolio Python pinning standard][pps] —
`requires-python = ">=3.11"` with no closed upper bound. Defensive upper
bounds belong in CI matrices, not in `requires-python`; the rationale and
recent stall incident this protects against are in the linked guide.

[pps]: https://github.com/appmilla/guardkit/blob/main/docs/guides/portfolio-python-pinning.md

Requirements:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip 23+

```bash
git clone https://github.com/appmilla/guardkitfactory.git
cd guardkitfactory

# uv (recommended)
uv sync --extra dev
uv run pytest tests/

# Or with plain pip
pip install -e ".[dev]"
pytest tests/
```

The falsifier for the scaffold task is:

```bash
uv sync && pytest tests/
python -c 'from guardkitfactory import HarnessAdapter; print(HarnessAdapter)'
```

## Layout

```
guardkitfactory/
├── pyproject.toml         # deepagents>=0.5,<1, langgraph>=1,<2, langchain>=1.2,<2
├── src/guardkitfactory/   # the installable package (src layout)
│   ├── __init__.py        # placeholder HarnessAdapter (TASK-HMIG-000R)
│   └── harness/           # receives LangGraphHarness in TASK-HMIG-001B
├── lib/                   # vendored helpers from the langchain-deepagents template
│   ├── factory_guards.py  # tool allowlisting + ainvoke() guard (TASK-REV-R2A1)
│   ├── json_extractor.py  # 5-strategy JSON extraction cascade
│   ├── retry_context.py   # retry-input + context manifest (Category C fix)
│   └── session_logging.py # per-run diagnostic JSON + logging bootstrap (Category A fix)
├── tests/
│   └── test_smoke.py
└── .github/workflows/ci.yml
```

`lib/` ships as a top-level package (configured via
`tool.setuptools.package-dir` in `pyproject.toml`) so that `from
lib.factory_guards import …` works after a `pip install -e .`. It is
deliberately *not* under `guardkitfactory/` — the helpers are template-
vendored and may be promoted up to the canonical template tree later.

## Cross-repo dependency

`guardkitfactory` is consumed by GuardKit's AutoBuild orchestrator. During
active development of the harness migration the typical workflow is:

```bash
# Sibling checkouts
~/Projects/appmilla_github/guardkit          # AutoBuild orchestrator
~/Projects/appmilla_github/guardkitfactory   # this repo

# Inside guardkit, install guardkitfactory editable:
cd ~/Projects/appmilla_github/guardkit
pip install -e ../guardkitfactory
```

Editable means changes here are picked up by `from guardkitfactory import
HarnessAdapter` in guardkit without a reinstall. Once the harness migration
is complete and a release is cut, guardkit will pin a published version.

## Develop alongside guardkit

If you are working harness tasks (`TASK-HMIG-*`) you'll typically want both
repos open:

1. **Branch in lock-step** — keep `guardkit` and `guardkitfactory` on
   matching feature branches when a harness change touches both sides.
2. **Editable install** — see the snippet above. The `guardkit` orchestrator
   imports `guardkitfactory` at autobuild dispatch time; an editable
   install means iterative changes don't require a reinstall.
3. **CI** — this repo's CI runs in isolation (it does not depend on
   `guardkit`). The `guardkit` repo runs an integration job that installs
   `guardkitfactory` from a pinned ref and exercises the harness end-to-end.
4. **Migrations** — task files under `tasks/` and migration notes under
   `migrations/` are committed *here*, not in `guardkit`, because the
   harness *is* the migration.

## Pin rationale (TASK-HMIG-000R §AC-001)

| Pin | Why |
|---|---|
| `deepagents>=0.5,<1` | `0.5.0` introduced the pluggable-backend protocol the LangGraph harness sits on top of (per `deepagents v0.5.0` changelog cited in parent review §14.7). The `<1` upper bound is a soft guard while the `0.5.x` line is well-supported; revisit when a `1.0` is on the horizon. |
| `langgraph>=1,<2`    | The harness targets the LangGraph 1.x API surface. |
| `langchain>=1.2,<2`  | Matches the LangChain `1.2` line `create_agent()` lives in. |
| `langchain-core>=1.2,<2` | Pinned in lock-step with `langchain` to avoid resolver drift. |
| `requires-python = ">=3.11"` | Portfolio canonical (no closed upper bound) — see [`portfolio-python-pinning.md`][pps]. |

## References

- Parent review: **TASK-REV-HMIG** — the autobuild harness migration
  (lives in the `guardkit` repo).
- Pinning standard: [`portfolio-python-pinning.md`][pps] in `guardkit`.
- Template source: `guardkit/installer/core/templates/langchain-deepagents/`
  — the lib helpers vendored here are derived directly from it.

## License

MIT — see [LICENSE](LICENSE).
