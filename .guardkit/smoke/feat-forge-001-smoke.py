#!/usr/bin/env python3
"""Feature-level smoke gate for FEAT-FORGE-001.

Runs between waves during ``/feature-build`` (or
``guardkit autobuild feature FEAT-FORGE-001``) to catch composition
failures the per-task Player-Coach loop cannot see.

The same command runs after every wave (``after_wave: "all"``). Each
check is best-effort and skips itself when the relevant modules are not
yet built — composition checks tighten as more waves complete.

Hard invariants enforced:

- **sc_001** — only one location in ``src/`` may issue
  ``UPDATE builds SET status``. The state_machine + persistence boundary.
- **import discipline** — ``cli/status.py`` and ``cli/history.py`` MUST
  NOT import from ``forge.adapters.nats.*``. The read path stays
  resilient to NATS being unreachable (Group H).
- **CLI smoke** — once Wave 5 has installed the ``console_scripts``
  entry, ``forge --help`` MUST succeed and list all five subcommands.

Exits 0 on pass, 1 on hard violation.
"""

from __future__ import annotations

import importlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"

REQUIRED_SUBCOMMANDS = ("queue", "status", "history", "cancel", "skip")


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _skip(msg: str) -> None:
    print(f"  · {msg} (skipped — modules not yet built)")


def _fail(msg: str) -> None:
    print(f"  ✗ {msg}", file=sys.stderr)


def check_sc_001_state_mutation_exclusivity() -> bool:
    """Hard invariant: at most one location may mutate builds.status."""
    if not SRC.exists():
        _skip("sc_001: src/ not present yet")
        return True

    pattern = re.compile(r"UPDATE\s+builds\s+SET\s+status", re.IGNORECASE)
    hits: list[Path] = []
    for path in SRC.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if pattern.search(text):
            hits.append(path.relative_to(REPO_ROOT))

    if len(hits) > 1:
        _fail(
            f"sc_001 violation: {len(hits)} locations mutate builds.status "
            f"(expected ≤ 1)"
        )
        for h in hits:
            print(f"      - {h}", file=sys.stderr)
        return False

    if hits:
        _ok(f"sc_001: single state-mutation site at {hits[0]}")
    else:
        _skip("sc_001: no state-mutation sites yet (state_machine + persistence not built)")
    return True


def check_import_discipline() -> bool:
    """Hard invariant: cli/status.py and cli/history.py MUST NOT import NATS."""
    bad_modules = ("forge.adapters.nats", "forge.adapters.nats.")
    targets = [
        SRC / "forge" / "cli" / "status.py",
        SRC / "forge" / "cli" / "history.py",
    ]

    any_present = False
    for path in targets:
        if not path.exists():
            continue
        any_present = True
        text = path.read_text(encoding="utf-8")
        for needle in bad_modules:
            if f"from {needle}" in text or f"import {needle}" in text:
                _fail(
                    f"import-discipline violation: {path.relative_to(REPO_ROOT)} "
                    f"imports from {needle}"
                )
                return False
        _ok(f"import discipline: {path.relative_to(REPO_ROOT)} clean")

    if not any_present:
        _skip("import discipline: cli/status.py and cli/history.py not yet built")
    return True


def check_foundation_imports() -> bool:
    """Best-effort: foundation modules import cleanly when present."""
    optional_imports = [
        "forge.lifecycle.identifiers",
        "forge.lifecycle.migrations",
        "forge.config.loader",
        "forge.lifecycle.state_machine",
        "forge.lifecycle.persistence",
        "forge.lifecycle.queue",
        "forge.lifecycle.recovery",
    ]

    any_imported = False
    for module_name in optional_imports:
        try:
            importlib.import_module(module_name)
            _ok(f"import: {module_name}")
            any_imported = True
        except ImportError:
            # Module not yet built — not an error in earlier waves
            pass
        except Exception as e:
            _fail(f"import error in {module_name}: {e}")
            return False

    if not any_imported:
        _skip("foundation imports: no lifecycle/config modules available yet")
    return True


def check_forge_cli_help() -> bool:
    """Wave 5+ check: forge --help works and lists all five subcommands."""
    if not shutil.which("forge"):
        _skip("forge --help: binary not on PATH (console_scripts not yet installed)")
        return True

    result = subprocess.run(
        ["forge", "--help"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if result.returncode != 0:
        _fail(f"forge --help exited {result.returncode}")
        print(result.stderr, file=sys.stderr)
        return False

    output = result.stdout
    missing = [c for c in REQUIRED_SUBCOMMANDS if c not in output]
    if missing:
        _fail(f"forge --help is missing subcommands: {missing}")
        return False

    _ok(f"forge --help: all five subcommands listed ({', '.join(REQUIRED_SUBCOMMANDS)})")
    return True


def main() -> int:
    print("[smoke] FEAT-FORGE-001 between-wave checks")
    checks = [
        check_sc_001_state_mutation_exclusivity,
        check_import_discipline,
        check_foundation_imports,
        check_forge_cli_help,
    ]
    failures = [c.__name__ for c in checks if not c()]
    if failures:
        print(f"\n[smoke] FAIL — {len(failures)} hard invariant(s) violated", file=sys.stderr)
        return 1
    print("\n[smoke] PASS — all between-wave checks satisfied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
