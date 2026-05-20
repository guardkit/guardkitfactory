"""BDD plugin loader: contract-gated registration and stack-based discovery.

The loader is the *type-system-level* guard against the §5 failure patterns
documented in parent review TASK-REV-HMIG. Every plugin registered with
:func:`register` has its :meth:`BDDPlugin.contract_tests` run synchronously;
any contract with ``passed=False`` refuses registration with
:class:`ContractTestFailure`.

There is no public way to add a plugin that bypasses :func:`register` — the
registry is module-private and the discovery iterator drives off it.
"""

from __future__ import annotations

from pathlib import Path

from guardkitfactory.bdd.plugin import BDDPlugin, StackProfile


class ContractTestFailure(RuntimeError):
    """Raised when a plugin fails one or more contract tests at registration."""


_REGISTRY: list[type[BDDPlugin]] = []


def register(plugin_cls: type[BDDPlugin]) -> type[BDDPlugin]:
    """Register a plugin after verifying its contract tests pass.

    Usable as a decorator on the plugin class. Constructs a minimal
    instance via ``__new__`` (no ``__init__`` side effects) and invokes
    :meth:`BDDPlugin.contract_tests`. Any contract with ``passed=False``
    raises :class:`ContractTestFailure` and the plugin is NOT added to
    the registry — by design.
    """
    instance = plugin_cls.__new__(plugin_cls)
    failures = [r for r in instance.contract_tests() if not r.passed]
    if failures:
        names = [f.contract_name for f in failures]
        details = "; ".join(f"{f.contract_name}: {f.detail}" for f in failures)
        raise ContractTestFailure(
            f"Plugin {plugin_cls.__name__} failed contract tests "
            f"{names}: {details}. This plugin cannot be registered until "
            "every failure-pattern guard is honoured "
            "(parent review TASK-REV-HMIG §6.2)."
        )
    if plugin_cls not in _REGISTRY:
        _REGISTRY.append(plugin_cls)
    return plugin_cls


def discover(stack: StackProfile, worktree: Path) -> BDDPlugin | None:
    """Return the first registered plugin whose :meth:`discover` matches."""
    for plugin_cls in _REGISTRY:
        match = plugin_cls.discover(stack, worktree)
        if match is not None:
            return match
    return None


def _registered_plugins() -> tuple[type[BDDPlugin], ...]:
    """Test helper: snapshot of the current registry."""
    return tuple(_REGISTRY)


def _clear_registry() -> None:
    """Test helper: empty the registry. Tests that re-register should use
    a context manager pattern (snapshot → clear → exercise → restore)."""
    _REGISTRY.clear()


__all__ = [
    "ContractTestFailure",
    "discover",
    "register",
]
