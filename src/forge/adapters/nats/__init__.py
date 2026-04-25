"""NATS adapter package — publishers and consumers for the fleet/pipeline streams.

Re-exports :class:`PipelinePublisher` and :class:`PublishFailure` from
:mod:`forge.adapters.nats.pipeline_publisher` so the canonical import path
``from forge.adapters.nats import PipelinePublisher`` resolves without
requiring callers to know the module layout.
"""

from forge.adapters.nats.pipeline_publisher import (
    PipelinePublisher,
    PublishFailure,
)

__all__ = ["PipelinePublisher", "PublishFailure"]
