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

from pathlib import Path

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.local_shell import LocalShellBackend

__all__ = ["build_autobuild_backend"]


# These match LocalShellBackend's call-site defaults rather than DeepAgents'
# library defaults — see the module docstring for why we override.
_AUTOBUILD_EXECUTE_TIMEOUT_SECONDS = 600
_AUTOBUILD_EXECUTE_MAX_OUTPUT_BYTES = 1_000_000

# Fixed, minimal PATH. The agent runs under operator trust but we still want a
# deterministic environment regardless of how the operator launched the
# orchestrator.
_AUTOBUILD_PATH = "/usr/bin:/bin"


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


def build_autobuild_backend(worktree: Path) -> CompositeBackend:
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

    Returns:
        A configured :class:`CompositeBackend` wrapping a
        :class:`LocalShellBackend`, ready to be passed to
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

    # TASK-HMIG-002R-SUMM-ROOT — wrap so SummarizationMiddleware's offload
    # prefix becomes ``<worktree>/conversation_history`` instead of literal
    # ``/conversation_history`` at host root. ``cwd`` (not ``root_dir``) is
    # the post-resolution absolute path so ``str()`` is stable.
    return CompositeBackend(
        default=local_shell,
        routes={},
        artifacts_root=str(local_shell.cwd),
    )
