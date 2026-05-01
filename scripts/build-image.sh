#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# scripts/build-image.sh — canonical Contract A producer for the forge
# production image (TASK-F009-005, FEAT-FORGE-009).
#
# Per scoping §11.4 Q4=(c), nats-core is resolved into the build via a
# BuildKit named context (``--build-context nats-core=../nats-core``).
# The relative ``../nats-core`` path is interpreted relative to the
# directory ``docker buildx`` is invoked from — that's why this script
# changes into ``forge/`` (the directory containing the Dockerfile)
# before running buildx, regardless of where the operator invokes the
# script from. From inside ``forge/``, ``../nats-core`` resolves to
# the sibling working tree (TASK-FORGE-FRR-003).
#
# Layout assumed:
#
#   …/appmilla_github/forge/                ← this project
#                    /scripts/build-image.sh ← this script
#   …/appmilla_github/nats-core/            ← sibling working tree
#
# After the cd, buildx runs from ``…/appmilla_github/forge/``, so:
#   * ``--build-context nats-core=../nats-core`` resolves to
#     ``…/appmilla_github/nats-core`` (the sibling).
#   * ``-f Dockerfile .`` references this project's Dockerfile and
#     uses ``forge/`` as the build context root.
#
# The canonical invocation matches RUNBOOK-FEAT-FORGE-008-validation.md
# §6.1 (LES1 §3 DKRX): the runbook and this script share the exact
# same ``docker buildx build ...`` line so a copy-paste from one to
# the other reproduces the build (TASK-F009-005 AC, B3 scenario).
#
# C3 scenario: if the BuildKit ``nats-core`` context is omitted (e.g.
# someone runs ``docker buildx build ... -f Dockerfile .`` directly
# without the ``--build-context`` flag), the build fails with a
# diagnostic naming the missing context. This script removes that
# foot-gun by always supplying the flag.
# ---------------------------------------------------------------------------

set -euo pipefail

# Resolve the script's own location and cd into forge/. The script
# lives at forge/scripts/build-image.sh, so one parent up from its
# dirname is forge/ — the directory whose Dockerfile we build and
# whose sibling ``../nats-core`` is the BuildKit named context source
# (TASK-FORGE-FRR-003).
FORGE_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$FORGE_DIR"

# Sanity check the sibling working tree before invoking buildx.
# Without this, the BuildKit ``--build-context nats-core=../nats-core``
# flag would silently dereference into a non-existent directory and
# the failure would surface deep inside the Dockerfile's COPY layer
# rather than here at the entry point. The path checked here MUST be
# the same path buildx will dereference (``../nats-core`` from inside
# forge/, i.e. the sibling working tree).
if [[ ! -d "../nats-core" ]]; then
    echo "ERROR: sibling working tree ../nats-core not found relative to ${FORGE_DIR}" >&2
    echo "       The BuildKit named context --build-context nats-core=../nats-core" >&2
    echo "       requires nats-core to be checked out as a sibling of forge/." >&2
    exit 1
fi

if [[ ! -d "../nats-core/src/nats_core" ]]; then
    echo "ERROR: ../nats-core does not contain src/nats_core — layout invalid" >&2
    echo "       Expected the canonical layout from RUNBOOK-FEAT-FORGE-008-validation.md." >&2
    exit 1
fi

# Canonical BuildKit invocation — Contract A producer. Do NOT alter
# this line without updating the runbook (§6.1) and the Dockerfile-side
# literal-match test in lockstep. The whitespace and argument order
# are part of the contract.
docker buildx build --build-context nats-core=../nats-core -t forge:production-validation -f Dockerfile .
