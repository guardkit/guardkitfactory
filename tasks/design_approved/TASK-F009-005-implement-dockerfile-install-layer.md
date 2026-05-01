---
complexity: 7
consumer_context:
- consumes: HEALTHZ_PORT
  driver: curl (apt-installed in runtime stage)
  format_note: Port 8080 — must literal-match forge.cli.serve.DEFAULT_HEALTHZ_PORT;
    mirrored as ENV FORGE_HEALTHZ_PORT=8080 in Dockerfile so HEALTHCHECK and runtime
    agree
  framework: Dockerfile HEALTHCHECK directive
  task: TASK-F009-001
created: 2026-04-30 00:00:00+00:00
dependencies:
- TASK-F009-001
- TASK-F009-002
feature_id: FEAT-FORGE-009
id: TASK-F009-005
implementation_mode: task-work
parent_review: TASK-REV-F009
priority: high
status: design_approved
tags:
- dockerfile
- buildkit
- nats-core
- install-layer
- healthcheck
- feat-forge-009
task_type: feature
test_results:
  coverage: null
  last_run: null
  status: pending
title: Implement Dockerfile install layer with BuildKit nats-core context and HEALTHCHECK
updated: 2026-04-30 00:00:00+00:00
wave: 2
---

# Task: Implement Dockerfile install layer with BuildKit `nats-core` context and HEALTHCHECK

## Description

Extend the T2 Dockerfile skeleton with the install layer that resolves
`nats-core` via the operator-decided **Q4 = (c) BuildKit named build
context** (scoping §11.4):

1. Builder stage `COPY --from=nats-core / /tmp/nats-core` — pulls the
   sibling working tree into the build via `--build-context
   nats-core=../nats-core`
2. Builder stage `uv pip install -e /tmp/nats-core` — installs nats-core
   editable from the COPYed path (matches the dev-host `[tool.uv.sources]`
   semantics without mutating `pyproject.toml`)
3. Builder stage `pip install .[providers]` — literal-match to runbook
   `RUNBOOK-FEAT-FORGE-008-validation.md` §0.4 and §6.1 (LES1 §3 DKRX)
4. Runtime stage `COPY --from=builder /opt/venv /opt/venv` — only the
   resolved venv crosses; no `gcc`/`build-essential` in runtime
5. Runtime stage `HEALTHCHECK CMD curl -fs http://localhost:8080/healthz
   || exit 1` (Contract B consumer)
6. Runtime stage `EXPOSE 8080`
7. NEW `scripts/build-image.sh` — canonical entry point that runs the
   BuildKit invocation from the parent directory and produces Contract A

Files created/edited:
- EDIT `Dockerfile` — install layer, HEALTHCHECK, EXPOSE
- NEW `scripts/build-image.sh` — wraps `docker buildx build
  --build-context nats-core=../nats-core -t forge:production-validation
  -f forge/Dockerfile forge/`

## Acceptance Criteria

- [ ] `scripts/build-image.sh` exists, is executable, and runs the
      canonical BuildKit invocation (Contract A producer):
      `docker buildx build --build-context nats-core=../nats-core -t
      forge:production-validation -f forge/Dockerfile forge/`
- [ ] Script must be invoked from forge's parent directory (resolves
      its own working dir via `cd "$(dirname "$0")/../.."`)
- [ ] `bash scripts/build-image.sh` succeeds on a fresh clone with the
      sibling `nats-core` working tree present (A1 scenario, AC-A)
- [ ] Builder stage runs `RUN test -d /tmp/nats-core/src/nats_core ||
      (echo "nats-core layout invalid" >&2; exit 1)` early-fail gate
      (R3 mitigation)
- [ ] When the BuildKit `nats-core` context is omitted, the build fails
      with a diagnostic naming the missing context (C3 scenario)
- [ ] Runtime venv contains `forge` as a regular installed distribution
      (no `.pth` editable pointer; C4 scenario)
- [ ] `pip install .[providers]` command in the Dockerfile literal-
      matches the runbook §0.4 and §6.1 install commands (B3 scenario,
      AC-E)
- [ ] `HEALTHCHECK` directive uses `curl -fs http://localhost:8080/healthz`
      (Contract B consumer; ASSUM-005)
- [ ] `ENV FORGE_HEALTHZ_PORT=8080` set in runtime stage so app and
      HEALTHCHECK agree
- [ ] `EXPOSE 8080` declared (and only 8080 — no other ports — E1.3)
- [ ] Built image, when run with `forge --help`, shows all 6 subcommands
      (queue, status, history, cancel, skip, serve) — A2 scenario
- [ ] Built image runs as non-root (UID 1000); inherits T2's user setup
- [ ] No real provider API keys in any layer (C1 scenario, AC-F)
- [ ] All modified files pass project-configured lint/format checks
      with zero errors (Dockerfile via `hadolint` if configured;
      shellcheck for `scripts/build-image.sh`)

## Test Requirements

- [ ] BuildKit invocation literal-match test: `scripts/build-image.sh`
      contains the Contract A canonical string (case-sensitive grep)
- [ ] Image-builds-from-fresh-clone test (T6 will run this end-to-end;
      this task adds a Dockerfile-side `RUN test -d` early-fail)
- [ ] No-editable-installs test: `pip show forge` inside the runtime
      image reports `Location: /opt/venv/lib/python3.14/site-packages`
      (not a path containing `src/forge`)
- [ ] HEALTHCHECK literal-match test: Dockerfile contains the literal
      string `curl -fs http://localhost:8080/healthz`

## Seam Tests

```python
"""Seam test: verify HEALTHZ_PORT contract from TASK-F009-001."""
import re
from pathlib import Path

import pytest


@pytest.mark.seam
@pytest.mark.integration_contract("HEALTHZ_PORT")
def test_healthz_port_dockerfile_match():
    """Verify the Dockerfile HEALTHCHECK port matches DEFAULT_HEALTHZ_PORT.

    Contract: Port 8080 — must literal-match forge.cli.serve.DEFAULT_HEALTHZ_PORT;
    mirrored as ENV FORGE_HEALTHZ_PORT=8080 in Dockerfile so HEALTHCHECK
    and runtime agree.
    Producer: TASK-F009-001
    """
    from forge.cli.serve import DEFAULT_HEALTHZ_PORT

    dockerfile = Path("Dockerfile").read_text()

    # ENV must mirror Python constant
    env_match = re.search(
        r"^ENV\s+FORGE_HEALTHZ_PORT=(\d+)\b", dockerfile, re.MULTILINE
    )
    assert env_match, "Dockerfile must declare ENV FORGE_HEALTHZ_PORT"
    assert int(env_match.group(1)) == DEFAULT_HEALTHZ_PORT, (
        f"Dockerfile ENV FORGE_HEALTHZ_PORT={env_match.group(1)} but "
        f"DEFAULT_HEALTHZ_PORT={DEFAULT_HEALTHZ_PORT}"
    )

    # HEALTHCHECK must hit the same port
    assert f"http://localhost:{DEFAULT_HEALTHZ_PORT}/healthz" in dockerfile, (
        "Dockerfile HEALTHCHECK must use the same port as DEFAULT_HEALTHZ_PORT"
    )
```

## Implementation Notes

The BuildKit `--build-context` semantics (per scoping §11.4):
- `--build-context nats-core=../nats-core` declares a named context
  resolvable in the Dockerfile via `COPY --from=nats-core ...`
- The relative path `../nats-core` is interpreted **relative to the
  directory `docker buildx` is invoked from** — that's why
  `scripts/build-image.sh` must `cd` to forge's parent directory before
  invoking buildx
- Inside the Dockerfile, `COPY --from=nats-core / /tmp/nats-core`
  mirrors the entire context root into a known absolute path

Do **not** mutate `pyproject.toml`'s `[tool.uv.sources]` entry inside
the Docker layer — scoping §11.4 explicitly preserves the dev-host
editable behaviour. The Docker layer rewrites resolution by COPYing
the named context to a known absolute path **before** `pip install
.[providers]` runs.

Two valid shim shapes for the install order:
- **(a)** `uv pip install -e /tmp/nats-core` first, then `pip install
  .[providers]` — recommended; matches dev-host editable semantics most
  closely, no pyproject mutation
- **(b)** rewrite a builder-stage-only copy of `pyproject.toml` to point
  at `/tmp/nats-core` absolute path — accepted but more invasive

Recommendation locked: use (a).