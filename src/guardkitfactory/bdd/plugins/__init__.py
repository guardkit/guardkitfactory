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

import logging
from typing import Any, Callable, Optional

from guardkitfactory.bdd.loader import ContractTestFailure

logger = logging.getLogger(__name__)


def _load(name: str, load: Callable[[], Any]) -> Optional[Any]:
    """Run ``load``, a static import of one built-in plugin (its
    ``@register`` runs), or log why that plugin is not registered."""
    try:
        return load()
    except ContractTestFailure as exc:
        logger.error("The %s BDD plugin is not registered: %s", name, exc)
        return None


def _cucumber_js() -> Any:
    from guardkitfactory.bdd.plugins.cucumber_js_plugin import CucumberJSPlugin

    return CucumberJSPlugin


def _pytest_bdd() -> Any:
    from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin

    return PytestBDDPlugin


def _reqnroll() -> Any:
    from guardkitfactory.bdd.plugins.reqnroll_plugin import ReqnrollPlugin

    return ReqnrollPlugin


CucumberJSPlugin = _load("CucumberJSPlugin", _cucumber_js)
PytestBDDPlugin = _load("PytestBDDPlugin", _pytest_bdd)
ReqnrollPlugin = _load("ReqnrollPlugin", _reqnroll)

__all__ = ["CucumberJSPlugin", "PytestBDDPlugin", "ReqnrollPlugin"]
