"""Built-in BDD plugins.

Importing this package triggers each plugin module's :func:`register`
decorator, which runs the plugin's :meth:`contract_tests` and adds it to
the registry iff every contract passes.

A built-in plugin whose contract checks fail is left unregistered and the
failure is logged (13 October 2026): it never takes down the import of
``guardkitfactory`` itself, which GuardKit needs for its shells and its
Coach whether or not any BDD plugin is usable. Its name below is then
``None``.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any, Optional

from guardkitfactory.bdd.loader import ContractTestFailure

logger = logging.getLogger(__name__)


def _load(module: str, name: str) -> Optional[Any]:
    """Import one built-in plugin module (its ``@register`` runs)."""
    try:
        loaded = importlib.import_module(f"{__name__}.{module}")
    except ContractTestFailure as exc:
        logger.error("The %s BDD plugin is not registered: %s", name, exc)
        return None
    return getattr(loaded, name)


CucumberJSPlugin = _load("cucumber_js_plugin", "CucumberJSPlugin")
PytestBDDPlugin = _load("pytest_bdd_plugin", "PytestBDDPlugin")
ReqnrollPlugin = _load("reqnroll_plugin", "ReqnrollPlugin")

__all__ = ["CucumberJSPlugin", "PytestBDDPlugin", "ReqnrollPlugin"]
