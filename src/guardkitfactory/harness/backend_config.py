"""LocalShellBackend factory for the AutoBuild LangGraph harness.

Why this module exists (TASK-HMIG-002R)
=======================================

Parent review TASK-REV-HMIG Revision 1 (decision D-03) replaces the v1 plan of
shipping custom ``@tool``-decorated ``read_file`` / ``write_file`` / ``edit_file``
/ ``bash`` implementations (≈22 hours of work) with a configured
``LocalShellBackend`` plus a ``FilesystemPermission`` deny-list. The built-in
DeepAgents tools (``ls``/``read_file``/``write_file``/``edit_file``/``glob``/
``grep``/``execute``) inherit from the backend for free, and the permissions
middleware enforces the deny-rules — there is no need to fork our own tool
implementations.

The companion module :mod:`guardkitfactory.harness.permissions` ships the
deny-rule list; this module ships the backend factory.

Why this returns a ``CompositeBackend`` (TASK-HMIG-002R-SUMM-ROOT, 2026-06-04)
-----------------------------------------------------------------------------

We wrap the ``LocalShellBackend`` in a ``CompositeBackend`` with
``artifacts_root=str(worktree)`` and an empty ``routes`` dict. The composite
is a pass-through for every operation — its only function here is to carry
the ``artifacts_root`` attribute that
``deepagents.middleware.summarization._DeepAgentsSummarizationMiddleware``
reads to compute its offload prefix
(``f"{artifacts_root.rstrip('/')}/conversation_history"``,
``summarization.py`` line 294-296 in deepagents 0.6.x). When the backend is
**not** a ``CompositeBackend``, the SDK falls back to ``"/"`` as the root —
producing a literal ``/conversation_history/<thread>.md`` write path.

That literal path collided fatally with TASK-HMIG-002R-NOVMODE's
``virtual_mode=False`` flip. Under ``virtual_mode=True``, the path would
have been silently re-rooted inside the worktree; under ``virtual_mode=False``
it now resolves to host root, which is read-only. The downstream symptom:
``SummarizationMiddleware`` cannot offload its first 60-message buffer
(``[Errno 30] Read-only file system: '/conversation_history'``), summarisation
aborts, and the next LLM call ships the full conversation, exceeding the
model's context window. Observed on qwen36-workhorse (131k ctx) in
``docs/reviews/autobuild-migration/autobuild-FEAT-AOF-run-2.md`` lines
342-350 with a 569,665-token prompt.

Wrapping in ``CompositeBackend(default=lsb, routes={}, artifacts_root=worktree)``
moves the offload prefix to ``<worktree>/conversation_history/`` — a real,
writable path. The composite is transparent for every other call: empty
``routes`` means every operation falls through to the ``LocalShellBackend``
default, preserving NOVMODE's literal-absolute-path semantics for
orchestrator-fed Coach JSON paths. NOVMODE and SUMM-ROOT are symmetric
fixes on the two ends of the same path-resolution gap:

* NOVMODE (Coach JSON writes): want absolute paths interpreted literally.
* SUMM-ROOT (conversation history writes): want SDK-hard-coded ``/conversation_history``
  re-rooted under the worktree.

The companion fix that makes summarisation actually *fire* on sub-Sonnet
context windows is TASK-HMIG-002R-MODEL-PROFILE in
:mod:`guardkitfactory.harness.model_config` — without it, the SDK's no-profile
fallback trigger (``("tokens", 170000)``) is larger than qwen's 131k context,
so summarisation never runs even when the offload path works.

Design rationale (AC-005)
=========================

``virtual_mode=False`` (TASK-HMIG-002R-NOVMODE, 2026-06-03)
-----------------------------------------------------------

Originally this was ``virtual_mode=True`` for filesystem-tool path-
confinement. AC-001D run 5 (see
``docs/reviews/autobuild-migration/TASK-FIX-A7D3-run-5.md``) showed why
that doesn't work for AutoBuild: the Coach LLM (and specialists) are fed
**absolute filesystem paths** by guardkit's orchestrator prompt
(``/Users/.../coach_turn_1.json``). Under ``virtual_mode=True``,
``LocalShellBackend`` interprets every path as virtual — rooted at
``root_dir`` — and silently prefixes the entire absolute string onto the
worktree, producing doubly-nested paths the orchestrator never finds:

  Coach asked to write:        /Users/.../<wt>/.guardkit/.../coach_turn_1.json
  LocalShellBackend wrote:     <wt>/Users/.../<wt>/.guardkit/.../coach_turn_1.json
  Orchestrator looked at:      /Users/.../<wt>/.guardkit/.../coach_turn_1.json

No error, no audit — the file just landed in the wrong place. The Coach's
verdict content was correct; only the plumbing was broken.

The security cost of flipping is documented and accepted:

* Upstream's own docs (cited in the original AC-005 rationale) note that
  ``virtual_mode=True`` "provides NO security with shell access enabled,
  since commands can access any path on the system". AutoBuild has
  shell access (``execute`` is required). The flag was only ever
  protecting filesystem-tool ``..`` traversal — which the SDK harness
  never had either (``permission_mode="acceptEdits"`` + ``cwd=worktree``
  does not sandbox path resolution at all). No regression vs the harness
  we're migrating from.

* Threat model (parent review §14.7 D-11): single-tenant, local-vLLM,
  operator-supervised runs. If that ever changes (multi-tenant or
  untrusted-model deployment) swap ``LocalShellBackend`` for a sandbox
  backend (Modal / Daytona / E2B) — that's a one-line change here.

The companion change in
:mod:`guardkitfactory.harness.permissions` (``TASK-HMIG-002R-NOPERMS``)
already removed the filesystem deny-rules, so the previously-claimed
"falsifier (d) guarantee" was already weakened. This flip closes the
remaining symptom rather than introducing a new gap.

``execute`` security still comes from the surrounding operator-trust
model plus the worktree boundary itself: the agent's ``cwd`` is the
worktree and ``inherit_env=False`` strips environment leakage.

``inherit_env=False``
---------------------

We pass an explicit ``env`` dict instead of inheriting the operator's
environment. The trade-off is uniformity over convenience: every AutoBuild
run sees the same ``PATH`` / ``HOME`` / ``TMPDIR`` regardless of which shell
the operator launched the orchestrator from. Avoids accidental leakage of
operator credentials (``AWS_PROFILE``, ``OPENAI_API_KEY``, …) into the
agent's subprocess environment, and means a CI run and a local run produce
the same ``execute`` behaviour.

``timeout=600`` and ``max_output_bytes=1_000_000``
--------------------------------------------------

DeepAgents' defaults are ``timeout=120`` (2 minutes) and
``max_output_bytes=100_000`` (≈100 KB). AutoBuild's Coach routinely runs the
full pytest suite via ``execute`` and exceeds both: a 300-test suite easily
runs past 2 minutes, and pytest's ``-v`` output for that many tests is well
over 100 KB. The override is intentional. If a Coach run still hits 600 s,
that is evidence of a test-suite hang and should be surfaced rather than
papered over with a larger value.

PolicyWrapper extension point (AC-006)
======================================

If GuardKit-specific atomic-write or backup-on-edit semantics are required
later, layer a ``PolicyWrapper`` around the returned backend per the
`deepagents/backends policy-hook pattern
<https://docs.langchain.com/oss/python/deepagents/backends>`_. Do **NOT**
fork custom ``@tool`` implementations — the permissions surface only
applies to the built-in tools (parent review §14.7), and a custom
``@tool`` would bypass them.
"""

from __future__ import annotations

import dataclasses
import logging
from pathlib import Path
from typing import Any

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.local_shell import LocalShellBackend

logger = logging.getLogger(__name__)

__all__ = ["build_autobuild_backend", "TruncatingBackend"]


# These match LocalShellBackend's call-site defaults rather than DeepAgents'
# library defaults — see the module docstring for why we override.
_AUTOBUILD_EXECUTE_TIMEOUT_SECONDS = 600
_AUTOBUILD_EXECUTE_MAX_OUTPUT_BYTES = 1_000_000

# Fixed, minimal PATH. The agent runs under operator trust but we still want a
# deterministic environment regardless of how the operator launched the
# orchestrator.
_AUTOBUILD_PATH = "/usr/bin:/bin"


def _truncate_text(text: str, limit: int, *, what: str) -> tuple[str, bool]:
    """Return ``text`` capped at ``limit`` chars with a visible marker.

    The marker is load-bearing, not cosmetic: a silently-dropped tail would
    let the Coach gather treat a partial read/grep/run as the whole thing —
    the false-confidence failure mode ``absence-of-failure-is-not-success.md``
    guards against. We mark exactly how many chars were elided so the model
    knows the evidence is incomplete. Returns ``(possibly_truncated, did_cut)``.
    """
    if limit <= 0 or len(text) <= limit:
        return text, False
    elided = len(text) - limit
    marker = (
        f"\n\n... [AutoBuild gather bound: {elided} more chars of {what} "
        f"truncated — re-read a narrower slice if you need them] ..."
    )
    return text[:limit] + marker, True


class TruncatingBackend:
    """Delegating backend wrapper that caps large tool-result payloads.

    TASK-PERF-COACHSYNTH (Lever A — "cap context growth"). The B-full Coach
    *gather* runs a tool-using agentic loop whose conversation grows by the
    full size of every ``read``/``grep``/``execute`` result. A single
    ``read`` of a 2,000-line file can dump tens of thousands of tokens into
    the running context in one cycle — enough to overshoot even a correctly-
    fired summarisation trigger (the "belt-and-braces" overshoot the
    ``model_config`` docstring calls out). This wrapper bounds each individual
    tool result to ``max_chars`` so no single cycle can blow the window.

    Scope: applied **only** to the Coach gather (the orchestrator passes
    ``max_tool_result_chars`` for that invocation alone). The Player and the
    toolless synthesis path get an unwrapped backend — the Player legitimately
    needs whole files to implement against, so truncation there would harm it.

    Mechanism: every attribute except the capped result-methods is delegated
    verbatim to ``inner`` via ``__getattr__`` (so ``cwd``, ``id``,
    ``artifacts_root`` and the full write/edit/ls/glob surface pass through
    unchanged). Only ``read``/``aread``, ``grep``/``agrep`` and
    ``execute``/``aexecute`` — the three big content producers — are
    overridden to truncate. Reconstruction uses :func:`dataclasses.replace`
    so the wrapper is robust to extra result fields; any non-dataclass result
    (or replace failure) falls back to the original, never breaking the call.
    """

    def __init__(self, inner: Any, max_chars: int) -> None:
        self._inner = inner
        self._max_chars = max_chars

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes NOT defined on this class — i.e. every
        # backend method/attribute except the overrides below.
        return getattr(self._inner, name)

    # -- read -------------------------------------------------------------
    def _cap_read(self, result: Any) -> Any:
        file_data = getattr(result, "file_data", None)
        if not isinstance(file_data, dict):
            return result
        content = file_data.get("content")
        if not isinstance(content, str):
            return result
        capped, did_cut = _truncate_text(content, self._max_chars, what="file content")
        if not did_cut:
            return result
        try:
            new_fd = dict(file_data)
            new_fd["content"] = capped
            return dataclasses.replace(result, file_data=new_fd)
        except Exception as exc:  # noqa: BLE001 — never break the tool call
            logger.debug("TruncatingBackend: read replace failed (%s)", exc)
            return result

    def read(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_read(self._inner.read(*args, **kwargs))

    async def aread(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_read(await self._inner.aread(*args, **kwargs))

    # -- execute ----------------------------------------------------------
    def _cap_execute(self, result: Any) -> Any:
        output = getattr(result, "output", None)
        if not isinstance(output, str):
            return result
        capped, did_cut = _truncate_text(output, self._max_chars, what="command output")
        if not did_cut:
            return result
        try:
            return dataclasses.replace(result, output=capped, truncated=True)
        except Exception as exc:  # noqa: BLE001 — never break the tool call
            logger.debug("TruncatingBackend: execute replace failed (%s)", exc)
            return result

    def execute(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_execute(self._inner.execute(*args, **kwargs))

    async def aexecute(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_execute(await self._inner.aexecute(*args, **kwargs))

    # -- grep -------------------------------------------------------------
    def _cap_grep(self, result: Any) -> Any:
        matches = getattr(result, "matches", None)
        if not isinstance(matches, list):
            return result
        kept: list[Any] = []
        budget = self._max_chars
        for match in matches:
            text = match.get("text", "") if isinstance(match, dict) else ""
            budget -= len(text)
            if budget < 0:
                break
            kept.append(match)
        if len(kept) == len(matches):
            return result
        dropped = len(matches) - len(kept)
        kept.append(
            {
                "path": "",
                "line": 0,
                "text": (
                    f"... [AutoBuild gather bound: {dropped} more grep "
                    f"match(es) truncated — narrow the pattern] ..."
                ),
            }
        )
        try:
            return dataclasses.replace(result, matches=kept)
        except Exception as exc:  # noqa: BLE001 — never break the tool call
            logger.debug("TruncatingBackend: grep replace failed (%s)", exc)
            return result

    def grep(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_grep(self._inner.grep(*args, **kwargs))

    async def agrep(self, *args: Any, **kwargs: Any) -> Any:
        return self._cap_grep(await self._inner.agrep(*args, **kwargs))


def _detect_venv_site_packages(worktree: Path) -> str | None:
    """Return the site-packages path under ``{worktree}/.venv`` if one exists.

    The AutoBuild worktree convention is to keep a ``.venv/`` at the repo
    root; surfacing ``site-packages`` via ``PYTHONPATH`` lets ``execute``
    run ``python -m pytest`` and friends without a separate activation step.
    Returns ``None`` if no venv is present — the agent will still work, it
    just won't see project-local installs from ``execute``.
    """
    venv_lib = worktree / ".venv" / "lib"
    if not venv_lib.is_dir():
        return None
    for python_dir in sorted(venv_lib.iterdir()):
        site_packages = python_dir / "site-packages"
        if site_packages.is_dir():
            return str(site_packages)
    return None


def build_autobuild_backend(
    worktree: Path,
    *,
    max_tool_result_chars: int | None = None,
) -> CompositeBackend:
    """Construct the AutoBuild backend for a given worktree (AC-001/002).

    Returns a :class:`CompositeBackend` whose ``default`` is the configured
    :class:`LocalShellBackend` and whose ``artifacts_root`` is the worktree.
    The composite carries no routes — every operation falls through to the
    underlying ``LocalShellBackend``. The only reason for the wrapper is to
    expose ``artifacts_root`` to deepagents' summarisation middleware so the
    SDK's hard-coded ``/conversation_history`` offload prefix is re-rooted
    under the worktree rather than at host root (TASK-HMIG-002R-SUMM-ROOT,
    see module docstring).

    The underlying ``LocalShellBackend`` is configured per the AC-002
    contract, as amended by TASK-HMIG-002R-NOVMODE (2026-06-03):

    * ``root_dir=worktree`` — the agent's filesystem root
    * ``virtual_mode=False`` — absolute paths resolve literally (was
      ``True``; flipped after AC-001D run 5 — see module docstring)
    * ``env`` — minimal explicit environment (``PATH``, ``HOME``,
      ``TMPDIR``, and ``PYTHONPATH`` if a ``.venv`` is detected)
    * ``inherit_env=False`` — no leakage from the operator's shell
    * ``timeout=600`` — 10-minute ``execute`` ceiling
    * ``max_output_bytes=1_000_000`` — 1 MB cap on ``execute`` output

    Tests and other consumers that need the underlying ``LocalShellBackend``
    (e.g. to assert ``virtual_mode`` / ``_env`` / ``_default_timeout``) can
    reach it via ``backend.default``.

    The companion :func:`guardkitfactory.harness.permissions.build_autobuild_permissions`
    factory returns the deny-rule list that should be passed alongside this
    backend to :class:`guardkitfactory.harness.LangGraphHarness`.

    Args:
        worktree: Filesystem path to the worktree the agent should operate
            inside. Does not have to exist yet — the backend resolves it on
            each call — but if it does not exist, ``.tmp`` and ``.venv``
            detection will silently no-op.
        max_tool_result_chars: TASK-PERF-COACHSYNTH. When set, each
            ``read``/``grep``/``execute`` result is capped at this many chars
            (with a visible truncation marker) via :class:`TruncatingBackend`,
            bounding how much a single tool cycle can add to the agent's
            running context. ``None`` (the default) leaves results uncapped —
            the Player and synthesis paths pass ``None``; only the Coach
            B-full gather passes a limit so its tool-using loop cannot
            overflow the model window (the run-22 TP05 F20 surface).

    Returns:
        A configured :class:`CompositeBackend` wrapping a
        :class:`LocalShellBackend` (optionally behind a
        :class:`TruncatingBackend`), ready to be passed to
        :class:`guardkitfactory.harness.LangGraphHarness`.
    """
    worktree = Path(worktree)

    env: dict[str, str] = {
        "PATH": _AUTOBUILD_PATH,
        "HOME": str(worktree),
        "TMPDIR": str(worktree / ".tmp"),
    }
    venv_site_packages = _detect_venv_site_packages(worktree)
    if venv_site_packages is not None:
        env["PYTHONPATH"] = venv_site_packages

    local_shell = LocalShellBackend(
        root_dir=worktree,
        virtual_mode=False,  # TASK-HMIG-002R-NOVMODE — see module docstring
        env=env,
        inherit_env=False,
        timeout=_AUTOBUILD_EXECUTE_TIMEOUT_SECONDS,
        max_output_bytes=_AUTOBUILD_EXECUTE_MAX_OUTPUT_BYTES,
    )

    # TASK-PERF-COACHSYNTH — optionally cap per-tool-result size for the
    # Coach gather. Compute artifacts_root from ``local_shell.cwd`` BEFORE
    # wrapping so the summarisation re-rooting is unaffected by the wrapper;
    # the TruncatingBackend then sits as the composite ``default`` and caps
    # read/grep/execute results. ``None`` leaves the backend unwrapped
    # (Player/synthesis behaviour unchanged).
    artifacts_root = str(local_shell.cwd)
    default_backend: Any = local_shell
    if max_tool_result_chars is not None:
        default_backend = TruncatingBackend(local_shell, max_tool_result_chars)

    # TASK-HMIG-002R-SUMM-ROOT — wrap so SummarizationMiddleware's offload
    # prefix becomes ``<worktree>/conversation_history`` instead of literal
    # ``/conversation_history`` at host root. ``cwd`` (not ``root_dir``) is
    # the post-resolution absolute path so ``str()`` is stable.
    return CompositeBackend(
        default=default_backend,
        routes={},
        artifacts_root=artifacts_root,
    )
