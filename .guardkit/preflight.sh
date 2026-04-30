#!/usr/bin/env bash
# .guardkit/preflight.sh — FEAT-FORGE-009 bootstrap pre-step (TASK-FIX-F09A1).
#
# Purpose
# -------
# GuardKit's environment_bootstrap is hardcoded to `pip install -e .`, which
# silently ignores `[tool.uv.sources]` in `forge/pyproject.toml`. PyPI has no
# wheel satisfying `nats-core>=0.3.0,<0.4` on Python 3.11/3.12, so bootstrap
# hard-fails before any task runs.
#
# This script seeds the worktree's venv with `nats-core` from the sibling
# source repo *before* GuardKit invokes `pip install -e .`. pip's resolver
# short-circuits when a dep is already satisfied, so the subsequent
# `pip install -e .` succeeds without ever consulting PyPI for nats-core.
#
# Why
# ---
# Forge-side ship-now fix per TASK-REV-F09A's decision review (Layer 1).
# Required *only until* TASK-FIX-F09A2 lands a durable fix in guardkit (or
# until TASK-FIX-F0E6b removes the need for [tool.uv.sources] entirely by
# republishing a working `nats-core` wheel).
#
# Usage
# -----
#   .guardkit/preflight.sh [worktree-path]
#
# Examples
#   ./.guardkit/preflight.sh                                  # uses $PWD
#   ./.guardkit/preflight.sh .guardkit/worktrees/FEAT-FORGE-009
#   FORGE_NATS_CORE_PATH=/path/to/nats-core ./.guardkit/preflight.sh
#
# Exit codes
# ----------
#   0  success (idempotent — re-running is safe)
#   1  sibling nats-core source missing or other unrecoverable error

set -euo pipefail

WORKTREE="${1:-$(pwd)}"

# ---------------------------------------------------------------------------
# 1. Resolve worktree to an absolute path
# ---------------------------------------------------------------------------
if [[ ! -d "$WORKTREE" ]]; then
    echo "preflight: ERROR worktree path '$WORKTREE' is not a directory" >&2
    exit 1
fi
WORKTREE="$(cd "$WORKTREE" && pwd)"

# ---------------------------------------------------------------------------
# 2. Resolve sibling nats-core repo
# ---------------------------------------------------------------------------
# Precedence:
#   (a) $FORGE_NATS_CORE_PATH if set
#   (b) <worktree>/../../../../nats-core — assumes the canonical
#       appmilla_github/{forge, nats-core} sibling layout, which is the
#       same assumption forge's [tool.uv.sources] already encodes.
#       From a worktree at .guardkit/worktrees/<branch>/ this resolves
#       to <forge>/../nats-core, i.e. the sibling repo.
if [[ -n "${FORGE_NATS_CORE_PATH:-}" ]]; then
    NATS_CORE_PATH="$FORGE_NATS_CORE_PATH"
else
    NATS_CORE_PATH="$WORKTREE/../../../../nats-core"
fi

if [[ ! -d "$NATS_CORE_PATH" ]]; then
    echo "preflight: ERROR sibling nats-core source not found at: $NATS_CORE_PATH" >&2
    echo "preflight:   Expected the canonical appmilla_github/{forge,nats-core} sibling layout." >&2
    echo "preflight:   Override with: FORGE_NATS_CORE_PATH=/abs/path/to/nats-core $0 $WORKTREE" >&2
    exit 1
fi
NATS_CORE_PATH="$(cd "$NATS_CORE_PATH" && pwd)"

# ---------------------------------------------------------------------------
# 3. Ensure worktree venv exists
# ---------------------------------------------------------------------------
VENV_DIR="$WORKTREE/.guardkit/venv"
if [[ ! -d "$VENV_DIR" ]]; then
    echo "preflight: creating venv at $VENV_DIR"
    mkdir -p "$WORKTREE/.guardkit"
    python3 -m venv "$VENV_DIR"
else
    echo "preflight: venv already exists at $VENV_DIR (reusing)"
fi
VENV_PYTHON="$VENV_DIR/bin/python"
if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "preflight: ERROR venv python not executable at $VENV_PYTHON" >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# 4. Seed nats-core into the venv (editable, from the sibling source)
# ---------------------------------------------------------------------------
# Plain pip is sufficient — see TASK-REV-F09A Reproduction B. Once nats-core
# is satisfied in the venv, pip's resolver short-circuits the unsatisfiable
# PyPI lookup when forge's own `pip install -e .` runs.
echo "preflight: installing nats-core (editable) from $NATS_CORE_PATH"
"$VENV_PYTHON" -m pip install -e "$NATS_CORE_PATH"

# ---------------------------------------------------------------------------
# 5. Defensive: place a symlink at <worktree>/.guardkit/worktrees/nats-core
# ---------------------------------------------------------------------------
# Future-proofs against the uv switch landing in TASK-FIX-F09A2: forge's
# [tool.uv.sources] declares `path = "../nats-core"`, which uv resolves
# relative to forge/pyproject.toml. From a worktree at
# .guardkit/worktrees/<branch>/, the literal `../nats-core` resolves to
# .guardkit/worktrees/nats-core — the symlink lets uv find the sibling
# without forge having to rewrite the path.
SYMLINK_DIR="$WORKTREE/.guardkit/worktrees"
SYMLINK_PATH="$SYMLINK_DIR/nats-core"
mkdir -p "$SYMLINK_DIR"
if [[ -L "$SYMLINK_PATH" ]]; then
    EXISTING_TARGET="$(readlink "$SYMLINK_PATH")"
    if [[ "$EXISTING_TARGET" == "$NATS_CORE_PATH" ]]; then
        echo "preflight: symlink already up to date: $SYMLINK_PATH -> $NATS_CORE_PATH"
    else
        echo "preflight: refreshing symlink (was -> $EXISTING_TARGET)"
        ln -sfn "$NATS_CORE_PATH" "$SYMLINK_PATH"
    fi
elif [[ -e "$SYMLINK_PATH" ]]; then
    echo "preflight: WARNING $SYMLINK_PATH exists and is not a symlink — leaving it alone" >&2
else
    echo "preflight: creating symlink $SYMLINK_PATH -> $NATS_CORE_PATH"
    ln -s "$NATS_CORE_PATH" "$SYMLINK_PATH"
fi

echo "preflight: done. Worktree $WORKTREE is ready for: pip install -e ."
