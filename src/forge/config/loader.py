"""YAML loader for ``forge.yaml``.

This module is the **integration contract producer** ``CONFIG_LOADER``
(see IMPLEMENTATION-GUIDE.md §4) consumed by the queue lifecycle
subsystem (TASK-PSM-008/009/010/011).

Design choices (TASK-PSM-003):

- ``yaml.safe_load`` is used so untrusted YAML cannot construct arbitrary
  Python objects. An empty file is normalised to an empty dict so the
  Pydantic root model can apply its own defaults.
- ``ForgeConfig.model_validate`` is invoked directly. Any
  ``pydantic.ValidationError`` raised during validation propagates to the
  caller **unchanged** — wrapping would hide structured error data the CLI
  needs to format actionable messages (AC-004 of TASK-PSM-003).
"""

from __future__ import annotations

from pathlib import Path

import yaml

from forge.config.models import ForgeConfig


def load_config(path: Path) -> ForgeConfig:
    """Read ``path`` as YAML and validate it against :class:`ForgeConfig`.

    Args:
        path: Filesystem location of the ``forge.yaml`` document.

    Returns:
        A validated :class:`ForgeConfig` instance.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        pydantic.ValidationError: If the YAML payload fails Pydantic
            validation. The exception is **not** wrapped — callers (the CLI
            in particular) catch ``ValidationError`` directly so they can
            format ``error.errors()`` for the operator.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return ForgeConfig.model_validate(raw)


__all__ = ["load_config"]
