"""Identifier validation and ``build_id`` derivation (TASK-PSM-001).

This module is the **security boundary** for any string that is later
interpolated into a worktree filesystem path or used as the ``build_id``
``PRIMARY KEY`` in the pipeline state-machine SQLite schema
(see ``API-cli.md §3.3`` and ``API-sqlite-schema.md §2.1``).

It implements concern ``sc_003`` from ``TASK-REV-3EEE``: validation depth
must catch URL-encoded traversal sequences (``%2F``, ``%2E%2E``,
double-encoded ``%252F``), null bytes that survive a single decode pass,
and any character outside the conservative allowlist
``[A-Za-z0-9_-]+``.

Public API
----------

* :class:`InvalidIdentifierError` — ``ValueError`` subclass carrying a
  structured ``reason`` attribute (``traversal``, ``null_byte``,
  ``disallowed_char``, or ``length``) so callers can branch on the
  failure mode without parsing the message string.
* :func:`validate_feature_id` — decode-then-allowlist validator.
* :func:`derive_build_id` — canonical ``build-{feature_id}-{YYYYMMDDHHMMSS}``
  composition.

Only stdlib imports are permitted (``re``, ``datetime``,
``urllib.parse``) — see the Coach Validation block in
``TASK-PSM-001-identifiers-and-traversal-validation.md``.
"""

from __future__ import annotations

import re
from datetime import datetime
from urllib.parse import unquote

__all__ = [
    "InvalidIdentifierError",
    "derive_build_id",
    "validate_feature_id",
]

# Allowlist for the post-decode form. Conservative on purpose: any
# filesystem-special character (``/``, ``\``, ``.``, ``:``, etc.) is
# rejected so the output is safe to interpolate into a worktree path or
# a SQLite ``PRIMARY KEY``.
_ALLOWED: re.Pattern[str] = re.compile(r"[A-Za-z0-9_-]+")

# Maximum length cap for ``feature_id``. Keeps interpolated paths well
# below typical filesystem ``NAME_MAX`` (255) limits even after the
# ``build-...-YYYYMMDDHHMMSS`` prefix/suffix are appended.
_MAX_LEN: int = 64

# Reason codes — kept as a module-level tuple so tests can reference the
# canonical set without duplicating the literals.
_VALID_REASONS: tuple[str, ...] = (
    "traversal",
    "null_byte",
    "disallowed_char",
    "length",
)


class InvalidIdentifierError(ValueError):
    """Raised when :func:`validate_feature_id` rejects an input.

    Attributes
    ----------
    value:
        The original (un-decoded) input the caller supplied. Preserved
        for log/audit lines so an operator can replay the exact bytes
        that were rejected.
    reason:
        One of ``"traversal"``, ``"null_byte"``, ``"disallowed_char"``,
        or ``"length"`` — see ``TASK-PSM-001`` AC-009. Callers can
        branch on this string without parsing :func:`str` of the
        exception.
    """

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"Invalid feature_id ({reason}): {value!r}")
        self.value = value
        self.reason = reason


def validate_feature_id(s: str) -> str:
    """Validate ``s`` as a ``feature_id`` and return its decoded form.

    The validator performs a **double** ``urllib.parse.unquote`` so that
    inputs like ``%252F`` (which decodes to ``%2F`` once and to ``/``
    twice) are caught. After decoding it enforces, in order:

    1. **Length** — must be in ``[1, 64]`` characters.
    2. **No null bytes** — ``\\x00`` is rejected even if it only appears
       after decoding.
    3. **Allowlist** — must match ``[A-Za-z0-9_-]+`` exactly. Inputs
       that would resolve to a filesystem traversal (``..``, ``/``,
       ``\\``) are reported with reason ``"traversal"``; all other
       allowlist failures are reported as ``"disallowed_char"``.

    Parameters
    ----------
    s:
        Untrusted input string (typically a CLI argument or an HTTP
        path parameter).

    Returns
    -------
    str
        The fully decoded ``feature_id`` (which equals ``s`` for inputs
        that contain no percent-encoded sequences).

    Raises
    ------
    InvalidIdentifierError
        With ``reason`` set to one of ``"length"``, ``"null_byte"``,
        ``"traversal"`` or ``"disallowed_char"``.
    """
    # Double-decode so ``%252F`` (the percent-encoded form of ``%2F``)
    # collapses to ``/`` and is caught by the allowlist check below.
    decoded = unquote(unquote(s))

    if not 1 <= len(decoded) <= _MAX_LEN:
        raise InvalidIdentifierError(s, "length")

    if "\x00" in decoded:
        raise InvalidIdentifierError(s, "null_byte")

    if not _ALLOWED.fullmatch(decoded):
        # Distinguish traversal-shaped inputs from generic disallowed
        # characters so audit logs can highlight likely attacks.
        if ".." in decoded or "/" in decoded or "\\" in decoded:
            raise InvalidIdentifierError(s, "traversal")
        raise InvalidIdentifierError(s, "disallowed_char")

    return decoded


def derive_build_id(feature_id: str, queued_at: datetime) -> str:
    """Compose the canonical ``build-{feature_id}-{YYYYMMDDHHMMSS}`` string.

    This is the format mandated by ``API-cli.md §3.3`` and
    ``API-sqlite-schema.md §2.1``.

    Parameters
    ----------
    feature_id:
        A previously-validated ``feature_id`` (callers SHOULD pass the
        return value of :func:`validate_feature_id` rather than raw
        user input).
    queued_at:
        The instant the build was queued. The naive/aware status of the
        ``datetime`` is preserved in :meth:`datetime.strftime`; the
        canonical pipeline producer uses UTC.

    Returns
    -------
    str
        ``"build-{feature_id}-{YYYYMMDDHHMMSS}"`` with the timestamp
        formatted via ``strftime("%Y%m%d%H%M%S")``.
    """
    return f"build-{feature_id}-{queued_at.strftime('%Y%m%d%H%M%S')}"
