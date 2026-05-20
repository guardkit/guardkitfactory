"""guardkitfactory.bdd: pluggable BDD oracle interface (TASK-HMIG-007).

Per parent review TASK-REV-HMIG §6, this package decouples "the BDD
oracle" from any single test runner. The :class:`BDDPlugin` ABC plus
:class:`BDDRunResult` is what the Coach reads; per-stack plugins know
how to invoke the underlying runner and parse its output into this
shared contract.

Importing this package auto-registers every built-in plugin (the
:mod:`guardkitfactory.bdd.plugins` package). The loader's
:func:`register` decorator runs each plugin's
:meth:`BDDPlugin.contract_tests` synchronously and refuses any plugin
with a failing contract — by design, so the §5 failure-pattern guards
are *non-negotiable*.
"""

from __future__ import annotations

from guardkitfactory.bdd.loader import ContractTestFailure, discover, register
from guardkitfactory.bdd.plugin import (
    BDDPlugin,
    BDDRunResult,
    ContractTestResult,
    Scenario,
    StackProfile,
)

# Side-effect import: registers every built-in plugin.
from guardkitfactory.bdd import plugins as _plugins  # noqa: F401

__all__ = [
    "BDDPlugin",
    "BDDRunResult",
    "ContractTestFailure",
    "ContractTestResult",
    "Scenario",
    "StackProfile",
    "discover",
    "register",
]
