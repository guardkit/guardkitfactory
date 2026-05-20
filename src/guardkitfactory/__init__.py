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

__version__ = "0.1.0"


class HarnessAdapter:
    """Placeholder for the LangGraph harness adapter (TASK-HMIG-000R).

    Concrete behaviour is implemented in:

    - TASK-HMIG-001B (``LangGraphHarness`` in :mod:`guardkitfactory.harness`)
    - TASK-HMIG-002R (backend configuration)

    Instantiation raises ``NotImplementedError`` on purpose — this symbol
    exists only so import-time consumers and the AC-002 smoke test have a
    stable public name to bind against while the real implementation is in
    flight.
    """

    def __init__(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "HarnessAdapter is a TASK-HMIG-000R placeholder. "
            "The concrete implementation lands in TASK-HMIG-001B "
            "(LangGraphHarness) and TASK-HMIG-002R (backend configuration)."
        )


__all__ = ["HarnessAdapter", "__version__"]
