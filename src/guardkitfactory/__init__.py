"""guardkitfactory: LangGraph-based harness for GuardKit AutoBuild.

Substrate package for the autobuild harness migration
(parent review TASK-REV-HMIG, feature FEAT-HMIG).

At this stage (TASK-HMIG-000R) only a placeholder ``HarnessAdapter`` symbol
is exposed so that downstream consumers can bind against a stable name
while the concrete implementation is being built:

- TASK-HMIG-001B → ``LangGraphHarness`` lands in :mod:`guardkitfactory.harness`
- TASK-HMIG-002R → pluggable backend configuration
- TASK-HMIG-007  → Player/Coach wiring

Do not instantiate ``HarnessAdapter`` — it raises ``NotImplementedError``
deliberately so accidental runtime use surfaces immediately.
"""

from __future__ import annotations

from guardkitfactory.harness import (
    LangGraphHarness,
    LangGraphHarnessError,
    build_autobuild_backend,
    build_autobuild_permissions,
)

__version__ = "0.1.0"


class HarnessAdapter:
    """Placeholder for the LangGraph harness adapter (TASK-HMIG-000R).

    Concrete behaviour is now available as :class:`LangGraphHarness` (see
    :mod:`guardkitfactory.harness`, landed in TASK-HMIG-001B). The real
    ABC is :class:`guardkit.orchestrator.harness.HarnessAdapter`;
    ``LangGraphHarness`` subclasses it directly. This placeholder is
    retained only for the TASK-HMIG-000R smoke-test contract (an
    instantiation attempt raises ``NotImplementedError`` so accidental
    runtime use surfaces immediately) and will be removed once that
    contract is migrated.
    """

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "HarnessAdapter is the TASK-HMIG-000R placeholder. "
            "Use guardkitfactory.LangGraphHarness (TASK-HMIG-001B) for the "
            "concrete LangGraph implementation, or "
            "guardkit.orchestrator.harness.HarnessAdapter for the ABC."
        )


__all__ = [
    "HarnessAdapter",
    "LangGraphHarness",
    "LangGraphHarnessError",
    "build_autobuild_backend",
    "build_autobuild_permissions",
    "__version__",
]
