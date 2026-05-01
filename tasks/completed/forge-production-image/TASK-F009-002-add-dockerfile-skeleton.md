---
complexity: 4
created: 2026-04-30 00:00:00+00:00
dependencies: []
feature_id: FEAT-FORGE-009
id: TASK-F009-002
implementation_mode: task-work
parent_review: TASK-REV-F009
priority: high
status: completed
tags:
- dockerfile
- scaffolding
- supply-chain
- feat-forge-009
task_type: scaffolding
test_results:
  coverage: null
  last_run: null
  status: completed
title: Add multi-stage Dockerfile skeleton with digest-pinned base and non-root user
updated: 2026-04-30 00:00:00+00:00
wave: 1
---

# Task: Add multi-stage Dockerfile skeleton with digest-pinned base and non-root user

## Description

Create the multi-stage Dockerfile skeleton at the forge repo root. Both
stages use `python:3.14-slim-bookworm` pinned to a sha256 digest (per
ASSUM-010 and ADR-ARCH-032). The runtime stage creates a non-root user
`forge` (UID 1000), sets `ENTRYPOINT ["forge"]`, and `CMD ["serve"]`.

T2 deliberately skips the install layer — that's T5's responsibility.
T2 produces an image that can `docker run forge:skel forge --help` and
exits cleanly as a non-root user.

Files created/edited:
- NEW `Dockerfile` at repo root — two stages (`builder`, `runtime`),
  both `FROM python:3.14-slim-bookworm@sha256:...`
- NEW `.dockerignore` — exclude `.git`, `.venv`, `.guardkit`, `tasks/`,
  `docs/`, `__pycache__`, `*.pyc`, `.pytest_cache`, `tests/`

## Acceptance Criteria

- [ ] `Dockerfile` exists at repo root with two named stages: `builder`
      and `runtime`
- [ ] Both `FROM` directives reference `python:3.14-slim-bookworm@sha256:`
      with a real sha256 digest pinned (no floating tag — E1.1 scenario)
- [ ] `runtime` stage creates a `forge` user with UID 1000 and switches
      to `USER forge` before `ENTRYPOINT` (C2 scenario, AC-G)
- [ ] `runtime` stage declares `ENTRYPOINT ["forge"]` and `CMD ["serve"]`
- [ ] No real provider API keys, no `.env` content, no SSH server, no
      remote-debugger surface in either stage (pre-emptive close on C1,
      E1.3)
- [ ] `.dockerignore` excludes `.git`, `.venv`, `.guardkit`, `tasks/`,
      `docs/`, `tests/`, `__pycache__`, `*.pyc`
- [ ] `docker build -f Dockerfile -t forge:skel .` succeeds against the
      skeleton (no install layer needed — `forge` binary won't exist yet,
      but the image must build)
- [ ] All modified files pass project-configured lint/format checks with
      zero errors

## Test Requirements

- [ ] Build smoke test: `docker build -f Dockerfile -t forge:skel-test .`
      exits 0 in CI
- [ ] Digest-pin lint: a `tests/dockerfile/test_digest_pinning.py` test
      greps the Dockerfile for `FROM python:3.14-slim-bookworm@sha256:`
      and asserts both stages match
- [ ] Non-root assertion: `docker run --rm forge:skel-test id -u`
      returns `1000` (or whatever UID the user resolves to)

## Implementation Notes

The sha256 digest of `python:3.14-slim-bookworm` must be looked up at
implementation time (`docker buildx imagetools inspect
python:3.14-slim-bookworm`). Pin both stages to the **same** digest;
update annotations should flag drift in T7's CI workflow.

The runtime stage cannot yet exec `forge` because the install layer
(T5) hasn't landed. That's expected — T2's smoke test is "image
builds and runs as non-root", not "image runs the CLI".