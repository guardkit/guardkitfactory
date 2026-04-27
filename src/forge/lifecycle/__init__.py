"""Forge lifecycle primitives — identifiers, build-id derivation, and other
helpers that are part of the pipeline state-machine security boundary.

This package is the canonical home for any helper that interpolates user-
supplied strings into a worktree path or a SQLite ``PRIMARY KEY``. Modules
here MUST treat their inputs as untrusted and reject anything outside the
declared allowlist.
"""

from forge.lifecycle.identifiers import (
    InvalidIdentifierError,
    derive_build_id,
    validate_feature_id,
)

__all__ = [
    "InvalidIdentifierError",
    "derive_build_id",
    "validate_feature_id",
]
