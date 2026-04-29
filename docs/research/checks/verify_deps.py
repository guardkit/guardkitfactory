#!/usr/bin/env python3
"""
Dependency verification for guardkit-py and forge on the GB10.

Run from the project root with:
    PYTHONPATH=src uv run python verify_deps.py

Or without uv:
    python verify_deps.py
"""

import importlib
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class DepCheck:
    pip_name: str
    import_name: str
    min_version: str | None = None
    group: str = "core"  # core, autobuild, falkordb, gemini, dev, forge


# ── guardkit core dependencies ──────────────────────────────────────
GUARDKIT_DEPS = [
    DepCheck("click", "click", "8.0.0"),
    DepCheck("rich", "rich", "13.0.0"),
    DepCheck("pyyaml", "yaml", "6.0.0"),
    DepCheck("python-frontmatter", "frontmatter", "1.0.0"),
    DepCheck("pydantic", "pydantic", "2.0.0"),
    DepCheck("Jinja2", "jinja2", "3.1.0"),
    DepCheck("python-dotenv", "dotenv", "1.0.0"),
    DepCheck("httpx", "httpx", "0.25.0"),
    DepCheck("graphiti-core", "graphiti_core", "0.5.0"),
    DepCheck("gherkin-official", "gherkin", "29.0.0"),
]

# ── guardkit optional: autobuild ────────────────────────────────────
GUARDKIT_AUTOBUILD = [
    DepCheck("claude-agent-sdk", "claude_agent_sdk", "0.1.49", group="autobuild"),
]

# ── guardkit optional: falkordb ─────────────────────────────────────
GUARDKIT_FALKORDB = [
    DepCheck("falkordb", "falkordb", None, group="falkordb"),
]

# ── guardkit optional: dev ──────────────────────────────────────────
GUARDKIT_DEV = [
    DepCheck("pytest", "pytest", "7.4.3", group="dev"),
    DepCheck("pytest-cov", "pytest_cov", "4.1.0", group="dev"),
    DepCheck("pytest-asyncio", "pytest_asyncio", "0.23.0", group="dev"),
    DepCheck("pytest-bdd", "pytest_bdd", "8.1", group="dev"),
]

# ── forge core dependencies ─────────────────────────────────────────
FORGE_DEPS = [
    DepCheck("deepagents", "deepagents", "0.5.3", group="forge"),
    DepCheck("langchain", "langchain", "1.2.11", group="forge"),
    DepCheck("langchain-core", "langchain_core", "1.2.18", group="forge"),
    DepCheck("langgraph", "langgraph", "0.2", group="forge"),
    DepCheck("langchain-community", "langchain_community", "0.3", group="forge"),
    DepCheck("langchain-anthropic", "langchain_anthropic", "0.2", group="forge"),
    DepCheck("nats-core", "nats_core", "0.2.0", group="forge"),
    # python-dotenv and pyyaml already in guardkit core
]

# ── forge optional: providers ───────────────────────────────────────
FORGE_PROVIDERS = [
    DepCheck("langchain-openai", "langchain_openai", "0.2", group="forge-providers"),
    DepCheck("langchain-google-genai", "langchain_google_genai", "2.0", group="forge-providers"),
]


def get_installed_version(pip_name: str) -> str | None:
    """Get installed version via importlib.metadata (most reliable)."""
    try:
        from importlib.metadata import version
        return version(pip_name)
    except Exception:
        return None


def check_importable(import_name: str) -> bool:
    """Check if a module can be imported."""
    try:
        importlib.import_module(import_name)
        return True
    except ImportError:
        return False


def version_gte(installed: str, minimum: str) -> bool:
    """Simple version comparison (handles major.minor.patch)."""
    from packaging.version import Version
    try:
        return Version(installed) >= Version(minimum)
    except Exception:
        # Fallback: naive tuple comparison
        try:
            inst = tuple(int(x) for x in installed.split(".")[:3])
            mini = tuple(int(x) for x in minimum.split(".")[:3])
            return inst >= mini
        except Exception:
            return False


def check_dep(dep: DepCheck) -> tuple[str, bool, str]:
    """Returns (status_emoji, passed, detail_message)."""
    importable = check_importable(dep.import_name)
    installed_ver = get_installed_version(dep.pip_name)

    if not importable and not installed_ver:
        return ("❌", False, f"NOT FOUND — pip install {dep.pip_name}")

    if not importable and installed_ver:
        return ("⚠️", False, f"installed ({installed_ver}) but import '{dep.import_name}' fails")

    if installed_ver and dep.min_version:
        if not version_gte(installed_ver, dep.min_version):
            return ("⚠️", False, f"{installed_ver} < required {dep.min_version}")

    ver_str = installed_ver or "version unknown"
    return ("✅", True, ver_str)


def run_checks(label: str, deps: list[DepCheck]) -> int:
    """Run checks for a group, return count of failures."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    failures = 0
    for dep in deps:
        emoji, passed, detail = check_dep(dep)
        if not passed:
            failures += 1
        pad = 30 - len(dep.pip_name)
        print(f"  {emoji} {dep.pip_name}{' ' * pad}{detail}")
    return failures


def main():
    print("=" * 60)
    print("  GuardKit + Forge Dependency Verification")
    print(f"  Python: {sys.version}")
    print(f"  Executable: {sys.executable}")
    print("=" * 60)

    # Try to import packaging for version comparison
    try:
        import packaging  # noqa: F401
    except ImportError:
        print("\n⚠️  'packaging' not installed — version comparisons will use fallback")

    total_failures = 0

    total_failures += run_checks("GuardKit — Core Dependencies", GUARDKIT_DEPS)
    total_failures += run_checks("GuardKit — AutoBuild (optional)", GUARDKIT_AUTOBUILD)
    total_failures += run_checks("GuardKit — FalkorDB (optional)", GUARDKIT_FALKORDB)
    total_failures += run_checks("GuardKit — Dev Tools (optional)", GUARDKIT_DEV)
    total_failures += run_checks("Forge — Core Dependencies", FORGE_DEPS)
    total_failures += run_checks("Forge — Provider Extras (optional)", FORGE_PROVIDERS)

    # ── Also check guardkit CLI entry point ─────────────────────────
    print(f"\n{'─' * 60}")
    print(f"  CLI Entry Points")
    print(f"{'─' * 60}")
    for cmd, module_path in [
        ("guardkit-py", "guardkit.cli.main"),
        ("forge", "forge.cli.main"),
    ]:
        try:
            importlib.import_module(module_path)
            print(f"  ✅ {cmd:30s}import {module_path} OK")
        except ImportError as e:
            total_failures += 1
            print(f"  ❌ {cmd:30s}import {module_path} FAILED: {e}")

    # ── Summary ─────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    if total_failures == 0:
        print("  ✅ All dependencies verified")
    else:
        print(f"  ❌ {total_failures} issue(s) found")
    print("=" * 60)

    return 1 if total_failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
