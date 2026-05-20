"""Built-in BDD plugins.

Importing this package triggers each plugin module's :func:`register`
decorator, which runs the plugin's :meth:`contract_tests` and adds it to
the registry iff every contract passes.
"""

from __future__ import annotations

# Side-effect imports: each module's @register decorator runs at import.
from guardkitfactory.bdd.plugins import (  # noqa: F401
    cucumber_js_plugin,
    pytest_bdd_plugin,
    reqnroll_plugin,
)
from guardkitfactory.bdd.plugins.cucumber_js_plugin import CucumberJSPlugin
from guardkitfactory.bdd.plugins.pytest_bdd_plugin import PytestBDDPlugin
from guardkitfactory.bdd.plugins.reqnroll_plugin import ReqnrollPlugin

__all__ = ["CucumberJSPlugin", "PytestBDDPlugin", "ReqnrollPlugin"]
