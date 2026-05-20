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

Design rationale (AC-005)
=========================

``virtual_mode=True``
---------------------

``LocalShellBackend``'s upstream docs explicitly note that ``virtual_mode=True``
"provides NO security with shell access enabled, since commands can access
any path on the system". Setting it anyway is deliberate. AutoBuild relies on
``virtual_mode=True`` for *filesystem-tool* path-confinement only:

* ``read_file`` / ``write_file`` / ``edit_file`` / ``ls`` / ``glob`` / ``grep``
  go through the backend's path-resolution layer, which blocks ``..`` and
  ``~`` traversal and treats ``root_dir`` as a virtual filesystem root. This
  is the falsifier (d) guarantee in TASK-HMIG-002R — a tool call that asks
  for ``../../../etc/passwd`` is rejected before it leaves the backend.

* ``execute`` security is *not* delivered by this flag. It comes from the
  surrounding operator-trust model (single-tenant, local-vLLM, an operator
  watching the run) plus the worktree boundary itself: the agent's
  ``cwd`` is the worktree and ``inherit_env=False`` strips environment
  leakage. If the threat model later requires production-grade isolation
  for ``execute``, parent review decision D-11 says to swap
  ``LocalShellBackend`` for a sandbox backend (Modal, Daytona, …) — that's
  a one-line change here.

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


def build_autobuild_backend(worktree: Path) -> LocalShellBackend:
    """Construct the AutoBuild ``LocalShellBackend`` for a given worktree (AC-001/002).

    The returned backend is configured per the AC-002 contract:

    * ``root_dir=worktree`` — the agent's filesystem root
    * ``virtual_mode=True`` — path-confinement for filesystem tools
    * ``env`` — minimal explicit environment (``PATH``, ``HOME``,
      ``TMPDIR``, and ``PYTHONPATH`` if a ``.venv`` is detected)
    * ``inherit_env=False`` — no leakage from the operator's shell
    * ``timeout=600`` — 10-minute ``execute`` ceiling
    * ``max_output_bytes=1_000_000`` — 1 MB cap on ``execute`` output

    The companion :func:`guardkitfactory.harness.permissions.build_autobuild_permissions`
    factory returns the deny-rule list that should be passed alongside this
    backend to :class:`guardkitfactory.harness.LangGraphHarness`.

    Args:
        worktree: Filesystem path to the worktree the agent should operate
            inside. Does not have to exist yet — the backend resolves it on
            each call — but if it does not exist, ``.tmp`` and ``.venv``
            detection will silently no-op.

    Returns:
        A configured :class:`LocalShellBackend` ready to be passed to
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

    return LocalShellBackend(
        root_dir=worktree,
        virtual_mode=True,
        env=env,
        inherit_env=False,
        timeout=_AUTOBUILD_EXECUTE_TIMEOUT_SECONDS,
        max_output_bytes=_AUTOBUILD_EXECUTE_MAX_OUTPUT_BYTES,
    )
