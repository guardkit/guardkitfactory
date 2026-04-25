"""NATS adapter package — publishers and consumers for the fleet/pipeline streams.

Re-exports the canonical entrypoints so callers can import from the
package root without knowing the module layout:

- :class:`PipelinePublisher` / :class:`PublishFailure` (lifecycle stream).
- :func:`register_on_boot`, :func:`heartbeat_loop`, :func:`deregister`
  plus the :class:`StatusProvider` and :class:`Clock` injection
  protocols (fleet self-registration).
- :class:`SyntheticResponseInjector` / :class:`SyntheticInjectFailure`
  (CLI cancel/skip steering — TASK-CGCP-008).
- :class:`ApprovalSubscriber` / :class:`ApprovalSubscriberDeps` /
  :class:`InvalidDecisionError` (inbound approval responses with
  short-TTL dedup buffer — TASK-CGCP-007).
"""

from forge.adapters.nats.approval_subscriber import (
    ApprovalSubscriber,
    ApprovalSubscriberDeps,
    InvalidDecisionError,
)
from forge.adapters.nats.fleet_publisher import (
    AGENT_ID,
    Clock,
    MonotonicClock,
    StatusProvider,
    deregister,
    heartbeat_loop,
    register_on_boot,
)
from forge.adapters.nats.pipeline_publisher import (
    PipelinePublisher,
    PublishFailure,
)
from forge.adapters.nats.synthetic_response_injector import (
    SyntheticInjectFailure,
    SyntheticResponseInjector,
)

__all__ = [
    "AGENT_ID",
    "ApprovalSubscriber",
    "ApprovalSubscriberDeps",
    "Clock",
    "InvalidDecisionError",
    "MonotonicClock",
    "PipelinePublisher",
    "PublishFailure",
    "StatusProvider",
    "SyntheticInjectFailure",
    "SyntheticResponseInjector",
    "deregister",
    "heartbeat_loop",
    "register_on_boot",
]
