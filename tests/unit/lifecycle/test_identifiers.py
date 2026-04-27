"""Unit tests for ``forge.lifecycle.identifiers`` (TASK-PSM-001).

Each test class maps to one or more acceptance criteria from
``tasks/backlog/TASK-PSM-001-identifiers-and-traversal-validation.md``:

* :class:`TestValidateFeatureIdHappyPath`        — AC-001 (canonical
                                                     ``feature_id`` round-trip)
* :class:`TestValidateFeatureIdTraversal`        — AC-002, AC-003, AC-004
                                                    (literal ``../``, single-
                                                    encoded ``%2E%2E%2F``,
                                                    double-encoded ``%252F``)
* :class:`TestValidateFeatureIdNullByte`         — AC-005 (null byte after
                                                    decode)
* :class:`TestValidateFeatureIdLength`           — AC-006, AC-007 (length
                                                    cap and empty input)
* :class:`TestValidateFeatureIdDisallowedChar`   — branch coverage for the
                                                    non-traversal allowlist
                                                    failure mode
* :class:`TestInvalidIdentifierErrorContract`    — AC-009 (subclass of
                                                    :class:`ValueError`,
                                                    structured ``reason``
                                                    attribute, value
                                                    preservation)
* :class:`TestDeriveBuildId`                     — AC-008 (canonical
                                                    ``build-...-YYYYMMDDHHMMSS``
                                                    composition)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from forge.lifecycle.identifiers import (
    InvalidIdentifierError,
    derive_build_id,
    validate_feature_id,
)


class TestValidateFeatureIdHappyPath:
    """AC-001: canonical ``feature_id`` round-trips unchanged."""

    def test_validate_feature_id_with_canonical_input_returns_same_string(
        self,
    ) -> None:
        # Arrange — the canonical FEAT-FORGE-001 identifier from §1
        feature_id = "FEAT-FORGE-001"

        # Act
        result = validate_feature_id(feature_id)

        # Assert
        assert result == "FEAT-FORGE-001"

    @pytest.mark.parametrize(
        "value",
        [
            "FEAT-FORGE-001",
            "feature_001",
            "ABC",
            "a",
            "A1",
            "_underscore_",
            "-leading-dash",
            "trailing-dash-",
            "MixedCase_123-X",
            "a" * 64,  # exactly at the length cap
        ],
    )
    def test_validate_feature_id_with_allowlisted_input_returns_input(
        self, value: str
    ) -> None:
        assert validate_feature_id(value) == value


class TestValidateFeatureIdTraversal:
    """AC-002 / AC-003 / AC-004: traversal sequences are rejected."""

    def test_validate_feature_id_with_literal_dot_dot_slash_raises_traversal(
        self,
    ) -> None:
        # AC-002
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("../etc/passwd")
        assert excinfo.value.reason == "traversal"

    def test_validate_feature_id_with_url_encoded_dot_dot_slash_raises_traversal(
        self,
    ) -> None:
        # AC-003
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("%2E%2E%2Fetc")
        assert excinfo.value.reason == "traversal"

    def test_validate_feature_id_with_double_encoded_slash_raises_traversal(
        self,
    ) -> None:
        # AC-004 — ``%252F`` ⇒ ``%2F`` ⇒ ``/`` after double decode
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("%252F")
        assert excinfo.value.reason == "traversal"

    @pytest.mark.parametrize(
        "value",
        [
            "..",
            "../",
            "../..",
            "foo/bar",
            "foo\\bar",
            "%2E%2E",
            "%2F",
            "%5C",  # backslash, single-encoded
        ],
    )
    def test_validate_feature_id_with_traversal_variants_raises_traversal(
        self, value: str
    ) -> None:
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id(value)
        assert excinfo.value.reason == "traversal"

    def test_traversal_error_preserves_original_value(self) -> None:
        # The original (still-encoded) string is preserved on the error
        # so audit logs can replay exactly what the caller sent.
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("%252F")
        assert excinfo.value.value == "%252F"


class TestValidateFeatureIdNullByte:
    """AC-005: null bytes (raw or decoded) are rejected."""

    def test_validate_feature_id_with_raw_null_byte_raises_null_byte(self) -> None:
        # AC-005 — literal NUL byte in the input
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("FEAT\x00")
        assert excinfo.value.reason == "null_byte"

    def test_validate_feature_id_with_url_encoded_null_byte_raises_null_byte(
        self,
    ) -> None:
        # ``%00`` decodes to ``\x00`` and must be caught.
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("FEAT%00BAR")
        assert excinfo.value.reason == "null_byte"


class TestValidateFeatureIdLength:
    """AC-006 / AC-007: length cap (64) and minimum (1)."""

    def test_validate_feature_id_with_input_above_length_cap_raises_length(
        self,
    ) -> None:
        # AC-006
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("a" * 65)
        assert excinfo.value.reason == "length"

    def test_validate_feature_id_with_empty_string_raises_length(self) -> None:
        # AC-007
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id("")
        assert excinfo.value.reason == "length"

    def test_validate_feature_id_at_length_cap_is_accepted(self) -> None:
        # Boundary — exactly 64 characters is allowed.
        boundary = "a" * 64
        assert validate_feature_id(boundary) == boundary

    def test_validate_feature_id_at_one_character_is_accepted(self) -> None:
        # Boundary — exactly 1 character is allowed.
        assert validate_feature_id("X") == "X"


class TestValidateFeatureIdDisallowedChar:
    """Branch coverage for the non-traversal allowlist failure mode."""

    @pytest.mark.parametrize(
        "value",
        [
            "feature id",  # whitespace
            "feature.id",  # dot but no traversal pattern
            "feature:id",  # colon
            "feature@id",  # at-sign
            "féature",  # non-ASCII letter
            "feature$id",  # shell metachar
        ],
    )
    def test_validate_feature_id_with_disallowed_char_raises_disallowed_char(
        self, value: str
    ) -> None:
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id(value)
        assert excinfo.value.reason == "disallowed_char"


class TestInvalidIdentifierErrorContract:
    """AC-009: ``InvalidIdentifierError`` subclasses ``ValueError`` with a
    structured ``reason`` attribute drawn from a fixed vocabulary."""

    def test_invalid_identifier_error_is_subclass_of_value_error(self) -> None:
        assert issubclass(InvalidIdentifierError, ValueError)

    def test_invalid_identifier_error_caught_as_value_error(self) -> None:
        # Existing callers that ``except ValueError`` keep working.
        with pytest.raises(ValueError):
            validate_feature_id("../etc")

    def test_invalid_identifier_error_carries_reason_attribute(self) -> None:
        err = InvalidIdentifierError("bad", "traversal")
        assert err.reason == "traversal"
        assert err.value == "bad"

    @pytest.mark.parametrize(
        ("value", "expected_reason"),
        [
            ("../x", "traversal"),
            ("FEAT\x00", "null_byte"),
            ("a" * 65, "length"),
            ("", "length"),
            ("feature.id", "disallowed_char"),
        ],
    )
    def test_reason_belongs_to_documented_vocabulary(
        self, value: str, expected_reason: str
    ) -> None:
        with pytest.raises(InvalidIdentifierError) as excinfo:
            validate_feature_id(value)
        assert excinfo.value.reason == expected_reason
        assert excinfo.value.reason in {
            "traversal",
            "null_byte",
            "disallowed_char",
            "length",
        }

    def test_invalid_identifier_error_message_includes_value_and_reason(self) -> None:
        err = InvalidIdentifierError("../etc", "traversal")
        text = str(err)
        assert "traversal" in text
        assert "../etc" in text


class TestDeriveBuildId:
    """AC-008: canonical ``build-{feature_id}-{YYYYMMDDHHMMSS}`` form."""

    def test_derive_build_id_with_canonical_inputs_returns_canonical_string(
        self,
    ) -> None:
        # AC-008 — the exact example from the task acceptance criteria.
        queued_at = datetime(2026, 4, 27, 12, 30, 45, tzinfo=UTC)
        result = derive_build_id("FEAT-FORGE-001", queued_at)
        assert result == "build-FEAT-FORGE-001-20260427123045"

    def test_derive_build_id_zero_pads_single_digit_components(self) -> None:
        # Single-digit month/day/hour/minute/second must zero-pad so the
        # resulting string sorts lexicographically by time.
        queued_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        assert derive_build_id("X", queued_at) == "build-X-20260102030405"

    def test_derive_build_id_ignores_microseconds(self) -> None:
        # The format string ``%Y%m%d%H%M%S`` truncates sub-second precision.
        with_micros = datetime(2026, 4, 27, 12, 30, 45, 999999, tzinfo=UTC)
        without_micros = datetime(2026, 4, 27, 12, 30, 45, tzinfo=UTC)
        assert derive_build_id("X", with_micros) == derive_build_id("X", without_micros)

    def test_derive_build_id_preserves_feature_id_verbatim(self) -> None:
        # The helper does not re-validate ``feature_id`` — it is a pure
        # composition. (Validation is the caller's responsibility, via
        # ``validate_feature_id``.)
        queued_at = datetime(2026, 4, 27, 12, 30, 45, tzinfo=UTC)
        assert derive_build_id("custom_id-42", queued_at) == (
            "build-custom_id-42-20260427123045"
        )

    def test_derive_build_id_accepts_non_utc_timezone(self) -> None:
        # The helper formats ``queued_at`` verbatim — no timezone
        # conversion. This documents the contract: callers wanting UTC
        # must pass a UTC-aware ``datetime`` themselves.
        plus_two = timezone(timedelta(hours=2))
        queued_at = datetime(2026, 4, 27, 14, 30, 45, tzinfo=plus_two)
        assert derive_build_id("X", queued_at) == "build-X-20260427143045"
