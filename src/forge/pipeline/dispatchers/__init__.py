"""Mode A specialist / subprocess stage dispatchers (FEAT-FORGE-007).

Dispatchers in this package are thin composition layers — they wire
:class:`forge.pipeline.forward_context_builder.ForwardContextBuilder`
(TASK-MAG7-006) onto the FEAT-FORGE-003 capability dispatch surface and
record the resulting ``stage_log`` lifecycle (submit + reply). They do
**not** re-implement specialist resolution, capability matching, or
correlation handling — those concerns are owned by FEAT-FORGE-003.

Today this package exposes the specialist-stage dispatcher used by the
``product-owner`` and ``architect`` stages (TASK-MAG7-007). The
subprocess and async-autobuild dispatchers (TASK-MAG7-008,
TASK-MAG7-009) land alongside this module without changing the public
surface — each new dispatcher adds its own module and re-exports its
``dispatch_*_stage`` entry point through this ``__init__``.
"""

from forge.pipeline.dispatchers.specialist import (
    SpecialistDispatchSurface,
    StageDispatchOutcome,
    StageDispatchResult,
    StageLogWriter,
    dispatch_specialist_stage,
)

__all__ = [
    "SpecialistDispatchSurface",
    "StageDispatchOutcome",
    "StageDispatchResult",
    "StageLogWriter",
    "dispatch_specialist_stage",
]
