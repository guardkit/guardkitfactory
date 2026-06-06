"""Unit tests for ``guardkitfactory.harness.model_config``.

Covers TASK-HMIG-002R-MODEL-PROFILE (2026-06-04):

* String spec → resolved BaseChatModel with profile attached for known models
* String spec → no profile attached for unknown models (SDK fallback preserved)
* BaseChatModel passthrough preserves identity and attaches profile when known
* Existing profile is never overridden (operator policy is a fallback, not a hint)

The string-spec tests patch deepagents' ``resolve_model`` at the model_config
import site so the tests do not depend on ``langchain-openai`` being installed
in the dev environment (production deployment installs it via
``.[providers]``; the dev venv may not). The patched stub mimics
``resolve_model``'s contract — return a ``BaseChatModel`` for a given string —
and the tests verify the profile-injection layer wrapping it.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from guardkitfactory.harness.model_config import (
    MODEL_CONTEXT_WINDOWS,
    resolve_autobuild_model,
)


# ---------------------------------------------------------------------------
# String spec resolution
# ---------------------------------------------------------------------------


def _fake_resolve(spec: str) -> FakeListChatModel:
    """Stand-in for deepagents' ``resolve_model`` — no real provider deps."""
    return FakeListChatModel(responses=["ok"])


def test_string_spec_for_known_model_attaches_profile() -> None:
    """qwen36-workhorse is registered with 131,072 tokens. Profile must land.

    Without the profile, deepagents' summarisation middleware would fall
    back to the 170 k-token trigger and the model would overflow context
    before summarisation fires. See ``autobuild-FEAT-AOF-run-2.md`` line 350.
    """
    with patch(
        "guardkitfactory.harness.model_config.resolve_model",
        side_effect=_fake_resolve,
    ):
        resolved = resolve_autobuild_model("openai:qwen36-workhorse")

    assert resolved.profile is not None
    assert resolved.profile["max_input_tokens"] == 131_072


def test_string_spec_for_unknown_model_leaves_profile_untouched() -> None:
    """Unknown models pass through. The SDK no-profile fallback applies.

    Operator policy adds models to ``MODEL_CONTEXT_WINDOWS`` explicitly —
    we never guess. Surfacing "no profile" cleanly preserves the existing
    behaviour for any model not yet registered.
    """
    with patch(
        "guardkitfactory.harness.model_config.resolve_model",
        side_effect=_fake_resolve,
    ):
        resolved = resolve_autobuild_model("openai:not-in-registry-model")

    assert resolved.profile is None


# ---------------------------------------------------------------------------
# BaseChatModel passthrough
# ---------------------------------------------------------------------------


def test_basechatmodel_passthrough_preserves_identity() -> None:
    """Pre-built BaseChatModel instances must not be re-resolved.

    The caller may have constructed the model with bespoke kwargs we should
    not silently drop (custom headers, retry policy, model_name override).
    """
    fake = FakeListChatModel(responses=["hello"])
    resolved = resolve_autobuild_model(fake)
    assert resolved is fake


def test_basechatmodel_with_existing_profile_is_not_overridden() -> None:
    """Operator policy is a fallback, not an override.

    If a partner package already populated ``profile`` (e.g.
    ``langchain-openai`` for genuine OpenAI models), keep theirs.
    """
    fake = FakeListChatModel(responses=["hello"])
    fake.profile = {"max_input_tokens": 999_999}
    resolved = resolve_autobuild_model(fake)
    assert resolved.profile == {"max_input_tokens": 999_999}


# ---------------------------------------------------------------------------
# Registry sanity
# ---------------------------------------------------------------------------


def test_registry_contains_qwen36_workhorse() -> None:
    """Regression — keep qwen36-workhorse in the registry until llama-swap drops it.

    Removing the entry without removing the deployment would silently re-
    expose the F11 overflow. If a future task retires qwen36, both this test
    and the deployment should be updated together.

    TASK-FIX-COACHBUDG01 (2026-06-06): shape changed from ``int`` to dict.
    """
    assert "qwen36-workhorse" in MODEL_CONTEXT_WINDOWS
    entry = MODEL_CONTEXT_WINDOWS["qwen36-workhorse"]
    assert isinstance(entry, dict), f"expected dict entry, got {type(entry)}"
    assert entry["ctx_size"] == 131_072
    assert entry["reasoning_mode"] == "off", "qwen36-workhorse needs --reasoning off per §3.2"


def test_registry_contains_gemma4_26b() -> None:
    """TASK-FIX-COACHBUDG01: gemma4:26b entry pins the Coach-swap (HMIG-013).

    Entry carries the larger max_tokens_coach budget (16384) that lets the
    model reason + emit structured output under --reasoning auto. Without
    this budget, hybrid-reasoning models squeeze reasoning_content +
    content and produce empty Coach turns — exactly the F17 failure mode
    the parser fallback was meant to close.
    """
    assert "gemma4:26b" in MODEL_CONTEXT_WINDOWS
    entry = MODEL_CONTEXT_WINDOWS["gemma4:26b"]
    assert isinstance(entry, dict)
    assert entry["ctx_size"] == 65_536
    assert entry["max_tokens_coach"] == 16_384, (
        "Coach budget must accommodate reasoning + structured output for "
        "hybrid-reasoning models — see §9.13 of AUTOBUILD-ON-LLAMA-SWAP findings."
    )
    assert entry["reasoning_mode"] == "auto", (
        "gemma4:26b runs with --reasoning auto in production once the parser "
        "fallback to reasoning_content lands (TASK-FIX-COACHBUDG01 AC-009)."
    )


def test_registry_entries_are_well_formed() -> None:
    """Every registry entry MUST be normalisable.

    A misconfigured zero or negative ctx_size would break
    ``compute_summarization_defaults``; a missing reasoning_mode default
    would surface as a registry lookup failure in operator tooling.
    """
    from guardkitfactory.harness.model_config import _normalize_entry

    for name, entry_raw in MODEL_CONTEXT_WINDOWS.items():
        entry = _normalize_entry(entry_raw)
        assert isinstance(entry["ctx_size"], int), f"{name}: ctx_size not int"
        assert entry["ctx_size"] > 0, f"{name}: ctx_size must be positive, got {entry['ctx_size']}"
        assert entry["reasoning_mode"] in ("off", "auto", "on"), (
            f"{name}: reasoning_mode must be off/auto/on, got {entry['reasoning_mode']!r}"
        )


def test_normalize_entry_accepts_legacy_int_shape() -> None:
    """Backwards compatibility: a callers writing legacy ``int`` entries still work.

    The pre-COACHBUDG01 shape was ``MODEL_CONTEXT_WINDOWS[name] = int``. The
    normalize helper bridges that to the new dict shape so downstream code
    doesn't need to branch on type.
    """
    from guardkitfactory.harness.model_config import _normalize_entry

    normalized = _normalize_entry(131_072)
    assert normalized["ctx_size"] == 131_072
    assert normalized["reasoning_mode"] == "auto", "legacy entries default to auto"
    assert normalized["max_tokens_coach"] is None, "legacy entries have no role budget"
    assert normalized["max_tokens_player"] is None


def test_get_reasoning_mode_returns_registry_policy() -> None:
    """``get_reasoning_mode`` consults the registry's policy field."""
    from guardkitfactory.harness.model_config import get_reasoning_mode

    assert get_reasoning_mode("qwen36-workhorse") == "off"
    assert get_reasoning_mode("gemma4:26b") == "auto"
    # Provider-prefixed spec is normalised.
    assert get_reasoning_mode("openai:gemma4:26b") == "auto"
    # Unknown model defaults to "auto" — the safest default.
    assert get_reasoning_mode("some-future-model") == "auto"
