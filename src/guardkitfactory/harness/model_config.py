"""Model resolution + profile/budget injection for the AutoBuild LangGraph harness.

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

TASK-FIX-COACHBUDG01 extension (2026-06-06)
--------------------------------------------

The §9.13 finding in ``docs/research/dgx-spark/AUTOBUILD-ON-LLAMA-SWAP-findings.md``
identified a second substrate-quality lever: **per-role `max_tokens` budget**.
Coach prompts under hybrid-reasoning models (Gemma 4 IT, DeepSeek V4 with
reasoning, Nemotron-3 with thinking, etc.) route generation through
``reasoning_content`` before producing ``content``. With Coach's narrow
``max_tokens`` budget the thinking phase never finishes, content never
emits, and the orchestrator sees an empty Coach turn — exactly the F17
failure mode TASK-FIX-COACHOUT01's Shape A parser was meant to close.

The robust fix is per-role budget injection at model-resolution time:

* Coach max_tokens: raised to 16384 by default (room for reasoning + content)
* Player/specialist max_tokens: stay at SDK defaults (typically 8192) unless
  a model registry entry overrides
* Per-model ``reasoning_mode`` metadata: ``"off"``, ``"auto"``, or ``"on"``
  — operator policy for the model's hybrid-reasoning routing behaviour

Registry shape change
~~~~~~~~~~~~~~~~~~~~~

Original shape (TASK-HMIG-002R-MODEL-PROFILE):

.. code-block:: python

    MODEL_CONTEXT_WINDOWS: dict[str, int] = {
        "qwen36-workhorse": 131_072,
    }

Extended shape (TASK-FIX-COACHBUDG01):

.. code-block:: python

    MODEL_CONTEXT_WINDOWS: dict[str, dict[str, Any]] = {
        "qwen36-workhorse": {
            "ctx_size": 131_072,
            "max_tokens_coach": 8192,
            "max_tokens_player": 8192,
            "reasoning_mode": "off",  # §3.2 of findings doc
        },
        "gemma4:26b": {
            "ctx_size": 65_536,
            "max_tokens_coach": 16_384,  # room for reasoning + structured output
            "max_tokens_player": 8192,
            "reasoning_mode": "auto",
        },
    }

Backwards compatibility: :func:`resolve_autobuild_model` accepts both the
legacy ``int`` shape and the new ``dict`` shape. An ``int`` entry is treated
as ``{"ctx_size": int, "reasoning_mode": "auto", max_tokens defaults to None}``.

The fix shape
-------------

This module exposes :func:`resolve_autobuild_model`, which:

1. Coerces a model spec (provider-prefixed string OR pre-built
   ``BaseChatModel``) to a ``BaseChatModel`` instance via deepagents'
   :func:`deepagents._models.resolve_model` (so the OpenRouter / OpenAI-
   responses defaults apply consistently with ``create_deep_agent``).
2. Looks up the model's entry in :data:`MODEL_CONTEXT_WINDOWS`
   (keyed by the bare model name — the part after ``provider:``).
3. Assigns ``model.profile = {"max_input_tokens": <ctx_size>}`` *only if*
   the model has no profile already AND the registry knows the model.
4. **TASK-FIX-COACHBUDG01**: if a ``role`` is provided AND the registry
   entry includes ``max_tokens_<role>``, applies the budget to the model
   via best-effort attribute assignment (``model.max_tokens = N``). Set
   silently fails for models that don't expose this attribute — the SDK's
   default budget then applies, matching pre-patch behaviour.

The registry is intentionally explicit rather than e.g. derived from
llama-swap's ``/v1/models`` metadata: the values are operator policy (we
choose the trigger threshold by knowing the deployed context size and the
empirically-validated max_tokens budget), not runtime state. Adding a model
takes a single line of dict.

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

import logging
from typing import Any, Final, Literal

from deepagents._models import resolve_model
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

__all__ = [
    "MODEL_CONTEXT_WINDOWS",
    "ReasoningMode",
    "resolve_autobuild_model",
    "get_reasoning_mode",
]


ReasoningMode = Literal["off", "auto", "on"]


# ---------------------------------------------------------------------------
# Registry — operator-known context windows + per-role max_tokens budgets +
# reasoning-mode policy for models we route through.
#
# Keys are the bare model name (the part after ``provider:``).
#
# Entry shape (dict):
#   ctx_size:           int. Real serving context in tokens — what llama-swap
#                       actually advertises for the deployment, not the model
#                       card's theoretical maximum. Drives the summarization
#                       trigger via ``model.profile["max_input_tokens"]``.
#   max_tokens_coach:   int | None. Generation budget for Coach role. Default
#                       16384 covers reasoning + structured output for hybrid-
#                       reasoning models. ``None`` = use SDK default.
#   max_tokens_player:  int | None. Generation budget for Player role. Default
#                       8192 matches SDK default; overridden only when an
#                       empirical reason exists. ``None`` = use SDK default.
#   reasoning_mode:     "off" | "auto" | "on". Operator policy for the
#                       model's hybrid-reasoning behaviour. Consumed by
#                       llama-swap server flags (operator-side, not by this
#                       module); recorded here as documentation. ``"off"``
#                       for models that produce structured output reliably
#                       without thinking; ``"auto"`` for hybrid-reasoning
#                       models where reasoning improves verdict quality
#                       (the COACHBUDG01 parser handles the routing).
#
# Legacy int shape is accepted for backwards compatibility — see
# resolve_autobuild_model below.
#
# qwen36-workhorse: llama-swap deployment of Qwen3.6-35B-A3B at
#   131,072-token serving context; sourced from the operator's llama-swap
#   ``config.yaml`` and confirmed by the error message in
#   ``autobuild-FEAT-AOF-run-2.md`` line 350: "n_ctx": 131072.
#   reasoning_mode "off" per §3.2 of the findings doc — qwen36-workhorse
#   emits prose before JSON when reasoning is auto; --reasoning off encoded
#   in its llama-swap config block makes the verdict-emission reliable.
#
# gemma4:26b: llama-swap deployment of Gemma 4 26B-A4B-IT UD-Q4_K_XL at
#   65,536-token serving context (matches the gemma4-coach config in §9.13
#   of the findings doc). reasoning_mode "auto" because the COACHBUDG01
#   parser fallback to reasoning_content + the bumped max_tokens budget
#   together make --reasoning off (the §9.13 workaround) unnecessary.
#   AC-009 of TASK-FIX-COACHBUDG01 verifies this empirically.
# ---------------------------------------------------------------------------
MODEL_CONTEXT_WINDOWS: Final[dict[str, dict[str, Any]]] = {
    "qwen36-workhorse": {
        "ctx_size": 131_072,
        "max_tokens_coach": 8192,
        "max_tokens_player": 8192,
        "reasoning_mode": "off",
    },
    "gemma4:26b": {
        "ctx_size": 65_536,
        "max_tokens_coach": 16_384,
        "max_tokens_player": 8192,
        "reasoning_mode": "auto",
    },
    # gemma4:31b: llama-swap deployment of Gemma 4 31B dense (QAT) at the
    #   98,304-token serving context the operator bumped to post-run-22
    #   (``coach31`` set, n_ctx 98304 — TASK-OPS-COACH31B). Registered by
    #   TASK-PERF-COACHSYNTH: before this entry the bare model name was
    #   ABSENT from the registry, so ``resolve_autobuild_model`` returned the
    #   model with ``profile=None`` and deepagents' summarisation middleware
    #   fell back to its fixed ``("tokens", 170000)`` trigger — LARGER than
    #   this 98,304 window. Summarisation therefore never fired and the
    #   B-full Coach gather grew its conversation unbounded until a single
    #   request hit 108,094 > 98,304 tokens and 400'd (F20, run-22 TP05). The
    #   profile injection below makes the fraction-based trigger fire at a
    #   safe fraction of the real window — the idiomatic root-cause half of
    #   the F20 fix (the harness recursion_limit + tool-result truncation are
    #   the defence-in-depth halves). reasoning_mode "auto": 31B is a
    #   hybrid-reasoning model and the COACHBUDG01 parser handles the routing.
    "gemma4:31b": {
        "ctx_size": 98_304,
        "max_tokens_coach": 16_384,
        "max_tokens_player": 8192,
        "reasoning_mode": "auto",
    },
}


def _bare_model_name(model_spec: str) -> str:
    """Return the part of a ``provider:model`` spec after the colon.

    ``"openai:qwen36-workhorse"`` -> ``"qwen36-workhorse"``. A spec without a
    colon is returned unchanged (the SDK accepts bare names in some providers).
    """
    _, separator, bare = model_spec.partition(":")
    return bare if separator else model_spec


def _normalize_entry(entry: int | dict[str, Any]) -> dict[str, Any]:
    """Coerce a registry entry to the new dict shape.

    Backwards-compatible bridge for callers (and tests) that still write
    legacy ``int`` entries — those are treated as ``ctx_size`` with no
    ``max_tokens`` override and ``reasoning_mode="auto"``.
    """
    if isinstance(entry, int):
        return {
            "ctx_size": entry,
            "max_tokens_coach": None,
            "max_tokens_player": None,
            "reasoning_mode": "auto",
        }
    return entry


def get_reasoning_mode(model_name: str) -> ReasoningMode:
    """Return the operator-policy reasoning_mode for a model.

    Used by callers (operator-side llama-swap config tooling, future
    `.claude/rules/` validators) to consult the registry's policy. Models
    not in the registry default to ``"auto"`` — the safest default given
    the COACHBUDG01 parser robustly handles either routing.
    """
    bare = _bare_model_name(model_name)
    entry = MODEL_CONTEXT_WINDOWS.get(bare)
    if entry is None:
        return "auto"
    return _normalize_entry(entry).get("reasoning_mode", "auto")  # type: ignore[return-value]


def resolve_autobuild_model(
    model: str | BaseChatModel,
    role: str | None = None,
) -> BaseChatModel:
    """Resolve a model spec to a ``BaseChatModel`` and inject profile + budget.

    Parameters
    ----------
    model:
        Either a provider-prefixed string (``"openai:qwen36-workhorse"``) or a
        pre-built ``BaseChatModel`` instance. The string form is resolved via
        :func:`deepagents._models.resolve_model` so the OpenRouter / OpenAI-
        responses defaults match ``create_deep_agent``'s own resolution path.
    role:
        Optional role identifier (``"coach"``, ``"player"``, etc.). When
        provided AND the registry entry includes ``max_tokens_<role>``, the
        budget is applied to the resolved model via best-effort attribute
        assignment. Default ``None`` skips role-specific budget injection.

    Returns
    -------
    BaseChatModel
        The resolved model, with ``model.profile`` populated from
        :data:`MODEL_CONTEXT_WINDOWS` when the model is known and does not
        already carry a profile, and ``model.max_tokens`` (or equivalent
        attribute) set when ``role`` matches a registry-defined budget.
        Unknown models pass through unchanged.

    Notes
    -----
    * The profile field is a Pydantic ``model_validator(mode="after")`` field
      on ``BaseChatModel`` (langchain-core 1.1+). Direct assignment is
      supported.
    * We only inject ``profile`` when ``model.profile is None``. If a partner
      package already populated it (e.g. ``langchain-openai`` for genuine
      OpenAI models), we keep theirs — operator policy is a *fallback*, not
      an override.
    * ``max_tokens`` attribute assignment is best-effort. ``ChatOpenAI``
      exposes ``max_tokens`` as a Pydantic field; partner providers may use
      different names (``max_completion_tokens``, ``max_output_tokens``, etc.).
      Assignment failures are logged at DEBUG and swallowed — the SDK's
      default budget then applies. The substrate-quality cost of the wrong
      budget for an unknown provider is small (max_tokens cap), and surfacing
      it as a failure here would block model resolution entirely.
    """
    if isinstance(model, str):
        bare = _bare_model_name(model)
        resolved = resolve_model(model)
    else:
        resolved = model
        identifier = _get_identifier(resolved)
        bare = identifier or ""

    entry_raw = MODEL_CONTEXT_WINDOWS.get(bare)
    if entry_raw is None:
        return resolved

    entry = _normalize_entry(entry_raw)
    ctx_size = entry["ctx_size"]

    # Layer 1 of TASK-HMIG-002R-MODEL-PROFILE: profile injection.
    if resolved.profile is None:
        resolved.profile = {"max_input_tokens": ctx_size}

    # Layer 2 of TASK-FIX-COACHBUDG01: per-role max_tokens.
    if role is not None:
        budget_key = f"max_tokens_{role}"
        budget = entry.get(budget_key)
        if budget is not None:
            _apply_max_tokens(resolved, budget, model_repr=bare, role=role)

    return resolved


def _apply_max_tokens(
    model: BaseChatModel,
    budget: int,
    *,
    model_repr: str,
    role: str,
) -> None:
    """Best-effort assignment of ``max_tokens`` (or equivalent) to a model.

    Tries the common attribute names in order: ``max_tokens`` (ChatOpenAI,
    most providers), ``max_completion_tokens`` (newer ChatOpenAI),
    ``max_output_tokens`` (Vertex AI / some partner classes). First
    successful assignment wins. All-fail logs DEBUG and continues — the
    SDK default budget then applies for that provider.
    """
    for attr_name in ("max_tokens", "max_completion_tokens", "max_output_tokens"):
        if hasattr(model, attr_name):
            try:
                setattr(model, attr_name, budget)
                logger.debug(
                    "TASK-FIX-COACHBUDG01: set %s.%s=%d for role=%r model=%r",
                    type(model).__name__,
                    attr_name,
                    budget,
                    role,
                    model_repr,
                )
                return
            except Exception as exc:  # noqa: BLE001 — best-effort
                logger.debug(
                    "TASK-FIX-COACHBUDG01: %s.%s = %d raised %s; trying next",
                    type(model).__name__,
                    attr_name,
                    budget,
                    exc.__class__.__name__,
                )
                continue
    logger.debug(
        "TASK-FIX-COACHBUDG01: no max_tokens-like attribute on %s for "
        "role=%r model=%r; SDK default budget applies.",
        type(model).__name__,
        role,
        model_repr,
    )


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
