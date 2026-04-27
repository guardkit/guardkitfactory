"""Build-mode taxonomy for FEAT-FORGE-008.

Defines the :class:`BuildMode` enum that the supervisor and Wave 2 planners
use to dispatch by chain shape. Three modes are recognised:

- ``MODE_A`` — full greenfield run (FEAT-FORGE-007), eight stages from
  ``product-owner`` through ``pull-request-review``.
- ``MODE_B`` — add-feature-to-existing-project (FEAT-FORGE-008 ASSUM-001),
  starts at ``/feature-spec`` and skips product-owner / architect /
  ``/system-arch`` / ``/system-design``.
- ``MODE_C`` — review-and-fix cycle (FEAT-FORGE-008 ASSUM-004), pairs
  ``/task-review`` with one ``/task-work`` per fix task and (optionally)
  terminates at a ``pull-request-review``.

This module deliberately lives in ``forge.lifecycle`` rather than
``forge.pipeline`` because the mode is a property of the build lifecycle,
not of any individual stage. Keeping the enum here means
:mod:`forge.pipeline.stage_taxonomy` can stay free of imports from
sibling ``forge.pipeline`` submodules (the import-cycle invariant from
TASK-MAG7-001) while the chain-data module
(:mod:`forge.pipeline.mode_chains_data`) can still import both
``StageClass`` and ``BuildMode`` cleanly.

References:
    - FEAT-FORGE-008 ASSUM-001 — Mode B chain.
    - FEAT-FORGE-008 ASSUM-004 — Mode C chain.
    - TASK-MBC8-001 — companion task that will persist ``mode`` on the
      ``Build`` SQLite row; this module is the canonical definition of
      the enum used both at runtime and on the wire.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["BuildMode"]


class BuildMode(StrEnum):
    """The three pipeline build modes.

    Members are ordered ``MODE_A``, ``MODE_B``, ``MODE_C`` so iteration
    follows the historical sequence in which the modes were specified
    (FEAT-FORGE-007 then FEAT-FORGE-008). String values mirror the
    dash-separated names that appear in build plans, persisted SQLite
    rows, and CLI flags so callers can round-trip between the enum and
    on-the-wire values without a translation table.
    """

    MODE_A = "mode-a"
    MODE_B = "mode-b"
    MODE_C = "mode-c"
