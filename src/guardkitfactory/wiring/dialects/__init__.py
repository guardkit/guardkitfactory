"""Wiring dialects: declarative per-language descriptors.

Side-effect import registers all built-in dialects in the global registry.
"""

from __future__ import annotations

import guardkitfactory.wiring.dialects.c_sharp  # noqa: F401
import guardkitfactory.wiring.dialects.javascript  # noqa: F401

# Side-effect imports: each module registers its dialect.
import guardkitfactory.wiring.dialects.python  # noqa: F401
import guardkitfactory.wiring.dialects.typescript  # noqa: F401
