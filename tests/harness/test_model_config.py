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
    """
    assert "qwen36-workhorse" in MODEL_CONTEXT_WINDOWS
    assert MODEL_CONTEXT_WINDOWS["qwen36-workhorse"] == 131_072


def test_registry_values_are_positive_integers() -> None:
    """A misconfigured zero or negative would break ``compute_summarization_defaults``."""
    for name, ctx in MODEL_CONTEXT_WINDOWS.items():
        assert isinstance(ctx, int), f"{name}: expected int, got {type(ctx)}"
        assert ctx > 0, f"{name}: context window must be positive, got {ctx}"
