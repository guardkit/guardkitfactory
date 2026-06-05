"""Model resolution + profile injection for the AutoBuild LangGraph harness.

Why this module exists (TASK-HMIG-002R-MODEL-PROFILE, 2026-06-04)
=================================================================

Companion to :mod:`guardkitfactory.harness.backend_config`'s SUMM-ROOT fix.
SUMM-ROOT moves the SummarizationMiddleware offload prefix into the worktree
so the *write* succeeds; this module ensures the *trigger* fires before the
model's context window overflows.

The defect this module addresses
--------------------------------

DeepAgents' :func:`deepagents.middleware.summarization.compute_summarization_defaults`
inspects ``model.profile["max_input_tokens"]`` (langchain-core 1.1+ field, see
``BaseChatModel.profile``) to decide whether to use a fraction-based trigger
(``("fraction", 0.85)``, i.e. summarise at 85% of the model's context) or a
fixed-token fallback (``("tokens", 170000)``, i.e. summarise at 170 k tokens
regardless of model). The fallback only suits Sonnet-class models — qwen36-
workhorse and any other ≤170 k model overflow their context window before
the trigger ever fires.

``init_chat_model("openai:qwen36-workhorse", ...)`` (deepagents' default
resolver) does not populate ``profile`` for non-OpenAI models routed through
the ``openai:`` provider stub, so without explicit injection every llama-swap-
hosted model on the operator's local stack runs in the no-profile fallback
and trips the same overflow that
``docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-2.md`` line 350
records (``request (569665 tokens) exceeds the available context size
(131072 tokens)``).

The fix shape
-------------

This module exposes :func:`resolve_autobuild_model`, which:

1. Coerces a model spec (provider-prefixed string OR pre-built
   ``BaseChatModel``) to a ``BaseChatModel`` instance via deepagents'
   :func:`deepagents._models.resolve_model` (so the OpenRouter / OpenAI-
   responses defaults apply consistently with ``create_deep_agent``).
2. Looks up the model's max-input-tokens in :data:`MODEL_CONTEXT_WINDOWS`
   (keyed by the bare model name — the part after ``provider:``).
3. Assigns ``model.profile = {"max_input_tokens": <ctx>}`` *only if* the
   model has no profile already AND the registry knows the model. Unknown
   models pass through unchanged (the SDK's no-profile fallback then applies,
   matching the pre-patch behaviour).

The registry is intentionally explicit rather than e.g. derived from
llama-swap's ``/v1/models`` metadata: the values are operator policy (we
choose the trigger threshold by knowing the deployed context size), not
runtime state. Adding a model takes a single line.

Belt-and-braces note
--------------------

Even with profile injection, summarisation can in principle still miss the
window if a single LLM turn produces a response large enough to overshoot
the (fraction × ctx) trigger in one step. The harness-level mitigation for
that lives in :mod:`guardkitfactory.harness.langgraph_harness` — see the
construction of the summarisation middleware list for how the message-count
ceiling is wired alongside the fraction trigger.
"""

from __future__ import annotations

from typing import Final

from deepagents._models import resolve_model
from langchain_core.language_models import BaseChatModel

__all__ = [
    "MODEL_CONTEXT_WINDOWS",
    "resolve_autobuild_model",
]


# ---------------------------------------------------------------------------
# Registry — operator-known context windows for models we route through.
#
# Keys are the bare model name (the part after ``provider:``). Values are the
# real serving context in tokens — what llama-swap actually advertises for
# the deployment, not the model card's theoretical maximum.
#
# qwen36-workhorse: llama-swap deployment of Qwen2.5-Coder-32B-Instruct at
#   131,072-token serving context; sourced from the operator's llama-swap
#   ``config.yaml`` and confirmed by the error message in
#   ``autobuild-FEAT-AOF-run-2.md`` line 350:
#       "n_ctx": 131072
#
# When adding a model: confirm against llama-swap's served limit, not the
# upstream model card. The two often disagree because llama-swap caps based
# on KV-cache memory available on the host.
# ---------------------------------------------------------------------------
MODEL_CONTEXT_WINDOWS: Final[dict[str, int]] = {
    "qwen36-workhorse": 131_072,
}


def _bare_model_name(model_spec: str) -> str:
    """Return the part of a ``provider:model`` spec after the colon.

    ``"openai:qwen36-workhorse"`` -> ``"qwen36-workhorse"``. A spec without a
    colon is returned unchanged (the SDK accepts bare names in some providers).
    """
    _, separator, bare = model_spec.partition(":")
    return bare if separator else model_spec


def resolve_autobuild_model(model: str | BaseChatModel) -> BaseChatModel:
    """Resolve a model spec to a ``BaseChatModel`` and inject profile if known.

    Parameters
    ----------
    model:
        Either a provider-prefixed string (``"openai:qwen36-workhorse"``) or a
        pre-built ``BaseChatModel`` instance. The string form is resolved via
        :func:`deepagents._models.resolve_model` so the OpenRouter / OpenAI-
        responses defaults match ``create_deep_agent``'s own resolution path.

    Returns
    -------
    BaseChatModel
        The resolved model, with ``model.profile`` populated from
        :data:`MODEL_CONTEXT_WINDOWS` when the model is known and does not
        already carry a profile. Unknown models pass through unchanged.

    Notes
    -----
    * The profile field is a Pydantic ``model_validator(mode="after")`` field
      on ``BaseChatModel`` (langchain-core 1.1+, see ``chat_models.py`` line
      361). Direct assignment is supported.
    * We only inject when ``model.profile is None``. If a partner package
      already populated the profile (e.g. ``langchain-openai`` for genuine
      OpenAI models), we keep theirs — operator policy is a *fallback*, not
      an override.
    """
    if isinstance(model, str):
        bare = _bare_model_name(model)
        resolved = resolve_model(model)
    else:
        resolved = model
        identifier = _get_identifier(resolved)
        bare = identifier or ""

    if resolved.profile is not None:
        return resolved

    ctx = MODEL_CONTEXT_WINDOWS.get(bare)
    if ctx is None:
        return resolved

    resolved.profile = {"max_input_tokens": ctx}
    return resolved


def _get_identifier(model: BaseChatModel) -> str | None:
    """Best-effort extraction of the bare model name from a BaseChatModel.

    Mirrors :func:`deepagents._models.get_model_identifier` but without
    importing it directly — keeps this module self-contained for the
    occasional case where a caller has hand-built a ``BaseChatModel`` and
    wants profile injection without re-routing through ``resolve_model``.
    """
    try:
        config = model.model_dump()
    except Exception:  # noqa: BLE001 — partner-class dumps can raise
        return None
    for key in ("model_name", "model"):
        value = config.get(key)
        if isinstance(value, str) and value:
            return value
    return None
