# guardkitfactory — GuardKit AutoBuild harness substrate

## Project Overview

`guardkitfactory` is the **LangGraph-backed execution harness** for the
[GuardKit](https://github.com/guardkit/guardkit) AutoBuild adversarial-cooperation
orchestrator. It is a **library**, not a standalone agent: guardkit's
orchestrator owns the Player/Coach loop and imports this package to run it.

What this package provides:

- **`guardkitfactory.harness`** — `LangGraphHarness` (a concrete subclass of
  `guardkit.orchestrator.harness.HarnessAdapter`) plus the backend, model, and
  permissions configuration that adapts it to different substrates:
  `build_autobuild_backend`, `resolve_autobuild_model`,
  `build_autobuild_permissions`, `MODEL_CONTEXT_WINDOWS`.
- **`guardkitfactory.bdd`** — the BDD contract surface the Coach's BDD bridge
  binds to: `discover`, `BDDRunResult`, `StackProfile`, `Scenario`, `BDDPlugin`.
- **`guardkitfactory.wiring`** — a deterministic (no-LLM) wiring/seam analyzer
  used by guardkit's post-wave wiring gate: `analyze_wiring` plus the
  CALLSITE_DRIFT, SYS_MODULES_TAMPER / env-tamper, PERMISSIVE_DOUBLE, and
  stub-scan checks (WS3-S3). Parsing is stack-agnostic via tree-sitter.
- **`guardkitfactory.lib`** — helpers vendored from the `langchain-deepagents`
  template (factory guards, JSON extraction, retry context, session logging).
  They live at `src/guardkitfactory/lib/`, *inside* the package namespace: a
  bare top-level `lib` package shadowed guardkit's `installer/core/lib` in the
  forge image (namespace-hygiene instance #3, 2026-08-04). Never move them back
  out.

`HarnessAdapter` (the top-level symbol) is a **retained placeholder** that
raises `NotImplementedError` — it exists only for the original TASK-HMIG-000R
smoke-test contract. Do not use it; use `LangGraphHarness`.

**Language**: Python (`requires-python = ">=3.12,<4"`)
**Runtime deps**: `deepagents==0.7.14`, `deepagents-code==0.1.69`,
`langgraph>=1.2,<2`, `langchain>=1.4,<2`, `langchain-core>=1.6.3,<2`,
`langchain-openai>=1.6,<2`, `tree-sitter>=0.25,<1`,
`tree-sitter-language-pack>=1.0,<2` (see `pyproject.toml` for per-pin rationale).

## Version & cross-repo seam

- **Published as v0.2.0** (annotated tag `v0.2.0`) — the first tagged release.
- Not on PyPI. guardkit resolves it **operator-side as an editable sibling**
  via `[tool.uv.sources]` (`../guardkitfactory`), pinned to the version
  contract `guardkitfactory>=0.2.0,<1`. The tag marks the exact commit the
  sibling checkout tracks.
- The contract boundary is CI-gated by `guardkit/.github/workflows/seam-tests.yml`
  ("Seam Tests (harness contract)"), which runs the `@pytest.mark.seam` tests
  against the real installed guardkitfactory on every guardkit PR/push. That
  workflow is the drift guard — do not weaken it. It tracks guardkitfactory's
  default branch (not a pinned tag) so it catches drift as it lands.

When you change a public symbol in `harness/`, `bdd/`, or `wiring/`, treat it
as a **seam change**: guardkit binds to it. Keep `__version__`
(`src/guardkitfactory/__init__.py`) and `[project].version` (`pyproject.toml`)
in sync — `tests/test_smoke.py` asserts they match.

## Quick Start

```bash
uv sync --extra dev        # or: pip install -e ".[dev]"
pytest tests/              # 300+ tests across harness/, bdd/, wiring/, smoke
```

The only optional-dependency group is `dev` (`pytest`, `pytest-bdd`, `ruff`,
`mypy`). There is no `providers` extra — the runtime deps above are declared in
`[project].dependencies` and install by default.

## Detailed Guidance

Rules load automatically when you work on relevant files:

- **Code Style**: `.claude/rules/code-style.md`
- **Testing**: `.claude/rules/testing.md`
- **Patterns**: `.claude/rules/patterns/`
- **Guidance**: `.claude/rules/guidance/`

The pattern rules under `.claude/rules/patterns/` (adversarial cooperation,
agent factory, memory injection, tool delegation, domain-driven configuration)
are **template-vendored background** carried over from the `langchain-deepagents`
template this package began as. They document the Player/Coach orchestration
pattern that *guardkit's* orchestrator implements and that the `guardkitfactory.lib` helpers
support — they do not describe a Player/Coach loop running inside this repo
(this repo has none; it is the harness the loop runs on).

### Pattern rule `Source:` path convention

Pattern rule files end with `Source: <path>` lines (e.g.
`Source: scaffold/orchestrator_pattern.py.template`). These paths are
**post-render** — they refer to the layout a user sees in a rendered
`langchain-deepagents` project, not paths inside this repo. Do not "correct"
them to match this tree.

## Python Pinning

`requires-python = ">=3.12,<4"` is the documented bound of the required
`deepagents-code==0.1.69` runtime. Keep it aligned with that direct dependency;
see `docs/guides/portfolio-python-pinning.md` in the guardkit repo for the
exception rule that applies when a runtime dependency narrows interpreter
support.

## See Also

- **Consumer / orchestrator**: [`guardkit`](https://github.com/guardkit/guardkit)
  — owns the AutoBuild Player/Coach loop and imports this harness.
- **README.md** — the human-facing status table, layout, and pin rationale.
