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

Moved out of the worktree (14 October 2026). Under the worktree, GuardKit's
checkpoint commit took the transcripts into the build's branch: build
FEAT-7F1D committed a 216 KB transcript, quoting the owner's home folder
throughout, to a public project. ``artifacts_root`` is now a private folder
in the worktree's own git directory (:func:`model_artifacts_root`), and the
composite routes ``<root>/conversation_history/`` and
``<root>/large_tool_results/`` to it, because the write fence below refuses
any write outside the worktree. The reason for the wrapper is unchanged: the
offload needs a real, writable path, and still gets one. Every other path
falls through to the default backend as before.

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

import atexit
import dataclasses
import logging
import os
import re
import shutil
import stat
import tempfile
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from deepagents.backends.composite import CompositeBackend
from deepagents.backends.filesystem import FilesystemBackend
from deepagents.backends.local_shell import LocalShellBackend
from deepagents.backends.protocol import (
    DeleteResult,
    EditResult,
    FileUploadResponse,
    SandboxBackendProtocol,
    WriteResult,
)

logger = logging.getLogger(__name__)

__all__ = [
    "build_autobuild_backend",
    "model_artifacts_root",
    "shell_home",
    "shell_tmpdir",
    "PathConfinedBackend",
    "TruncatingBackend",
]


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
        if self._max_chars <= 0 or len(content) <= self._max_chars:
            return result

        # Keep pagination metadata truthful. Cutting arbitrary characters
        # while retaining the inner backend's end_line/next_offset makes a
        # partial read look complete. When line metadata is available, keep
        # only whole source lines and point next_offset at the first omitted
        # line. A single long line is kept intact rather than misreported.
        start_line = getattr(result, "start_line", None)
        end_line = getattr(result, "end_line", None)
        if isinstance(start_line, int) and isinstance(end_line, int):
            lines = content.splitlines(keepends=True)
            kept: list[str] = []
            size = 0
            for line in lines:
                if kept and size + len(line) > self._max_chars:
                    break
                kept.append(line)
                size += len(line)
            if len(kept) == len(lines):
                return result
            capped = "".join(kept)
            truthful_end = start_line + len(kept) - 1
            replacements = {
                "end_line": truthful_end,
                "next_offset": truthful_end,
            }
        else:
            capped, _ = _truncate_text(
                content, self._max_chars, what="file content"
            )
            replacements = {}
        try:
            new_fd = dict(file_data)
            new_fd["content"] = capped
            return dataclasses.replace(result, file_data=new_fd, **replacements)
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

    # ``timeout`` must be a NAMED parameter (not swallowed by ``**kwargs``):
    # ``deepagents.backends.composite.execute_accepts_timeout`` introspects
    # the class-level signature and only forwards per-call timeout overrides
    # when it finds the name. With ``*args, **kwargs`` the override was
    # silently dropped on the Coach-gather path (TASK-FIX-WTESCAPE01 review).
    def execute(self, command: str, *, timeout: int | None = None) -> Any:
        return self._cap_execute(self._inner.execute(command, timeout=timeout))

    async def aexecute(self, command: str, *, timeout: int | None = None) -> Any:
        return self._cap_execute(
            await self._inner.aexecute(command, timeout=timeout)
        )

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

    # Deep Agents 0.7 checks for class-level delete support before exposing
    # the tool. Explicit passthroughs keep delete available through this
    # otherwise transparent gather wrapper.
    def delete(self, file_path: str) -> Any:
        return self._inner.delete(file_path)

    async def adelete(self, file_path: str) -> Any:
        return await self._inner.adelete(file_path)


# TASK-FIX-WTESCAPE01: ``CompositeBackend.execute`` gates on
# ``isinstance(default, SandboxBackendProtocol)`` — an ABC, so structural
# delegation via ``__getattr__`` does not satisfy it. Without registration a
# wrapped default raises ``NotImplementedError`` on the first ``execute``
# (latent since TASK-PERF-COACHSYNTH for the Coach-gather path; surfaced when
# PathConfinedBackend became the always-on default).
SandboxBackendProtocol.register(TruncatingBackend)


class PathConfinedBackend:
    """Delegating backend wrapper that confines file mutations to allowed roots.

    TASK-FIX-WTESCAPE01 (2026-06-12). ``virtual_mode=False`` (NOVMODE)
    deliberately removed the SDK's path-confinement so orchestrator-fed
    absolute paths *inside* the worktree resolve literally. The unpriced
    side-effect: the Player's ``write_file``/``edit_file`` also honour
    absolute paths *outside* the worktree — FEAT-C332 run 2 observed Player
    edits landing in the operator's main guardkit checkout because the task
    context contained absolute host-repo paths.

    This wrapper restores confinement for the mutating file tools only:

    * ``write``/``awrite`` and ``edit``/``aedit`` resolve the target
      (``Path.resolve()`` — symlink-aware, so an in-worktree symlink
      pointing outside cannot smuggle a write out) and reject any path
      whose resolved form is not under an allowed root. Rejection is a
      tool error (``WriteResult``/``EditResult`` with ``error`` set), never
      an exception — the model gets actionable feedback to retry with a
      worktree-relative path. Each rejection logs a WARNING so operators
      see confinement doing work (AC-004).
    * Reads, ``ls``, ``glob``, ``grep`` stay unconfined — the Coach
      legitimately reads orchestrator-fed absolute paths, and reads cannot
      corrupt the host repo. ``execute`` is likewise out of scope per the
      documented operator-trust threat model (see NOVMODE rationale above);
      shell confinement was never claimed by this layer.
    * ``upload_files`` is not exposed as an LLM tool, so it is not wrapped.

    Rejecting (rather than rebasing the path into the worktree) is
    deliberate: silent rebasing is exactly the doubly-nested-path failure
    NOVMODE exists to prevent, in the opposite direction.

    Allowed roots beyond the worktree are an explicit policy decision made
    by :func:`build_autobuild_backend` — see its ``extra_write_roots``
    parameter and the intentional ``guardkitfactory`` sibling-symlink
    convention (AC-002).

    Delegation follows the :class:`TruncatingBackend` pattern: every
    attribute except the explicitly overridden mutators passes through to
    ``inner`` via ``__getattr__``, so ``cwd``, ``id``, ``artifacts_root``
    and the whole read surface are untouched.
    """

    def __init__(
        self,
        inner: Any,
        allowed_roots: Sequence[Path],
        protected_paths: Sequence[Path | str] = (),
        scratch_root: Path | str | None = None,
    ) -> None:
        self._inner = inner
        self._allowed_roots = [Path(root).resolve() for root in allowed_roots]
        # Named in the refusal so a builder that aimed a throwaway script
        # outside the worktree is told where such files may go.
        self._scratch_root = (
            Path(scratch_root).resolve() if scratch_root is not None else None
        )
        worktree = self._allowed_roots[0]
        protected_files: set[Path] = set()
        protected_directories: set[Path] = set()
        protected_file_aliases: set[Path] = set()
        protected_directory_aliases: set[Path] = set()
        for raw in protected_paths:
            candidate = Path(raw)
            if not candidate.is_absolute():
                candidate = worktree / candidate
            lexical = self._absolute_path(candidate)
            try:
                resolved = candidate.resolve(strict=True)
            except (OSError, RuntimeError) as exc:
                raise ValueError(f"protected path does not exist: {raw}") from exc
            if not resolved.is_relative_to(worktree):
                raise ValueError(f"protected path escapes the worktree: {raw}")
            if resolved.is_dir():
                protected_directories.add(resolved)
                protected_directory_aliases.add(lexical)
            elif resolved.is_file():
                protected_files.add(resolved)
                protected_file_aliases.add(lexical)
            else:
                raise ValueError(f"protected path is not a file or directory: {raw}")
        self._protected_files = frozenset(protected_files)
        self._protected_directories = frozenset(protected_directories)
        self._protected_file_aliases = frozenset(protected_file_aliases)
        self._protected_directory_aliases = frozenset(protected_directory_aliases)

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes NOT defined on this class — i.e. every
        # backend method/attribute except the four confined mutators below.
        return getattr(self._inner, name)

    @property
    def scratch_root(self) -> Path | None:
        """The scratch folder this backend allows, or ``None``.

        guardkit reads it to name the folder to the builder and to leave
        its files off the builder's lists only when it is really writable.
        """
        return self._scratch_root

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve a backend path exactly where the mutation would land."""
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = Path(self._inner.cwd) / candidate
        return candidate.resolve()

    def _absolute_path(self, file_path: str | Path) -> Path:
        """Return an absolute lexical path without resolving symlinks."""
        candidate = Path(file_path)
        if not candidate.is_absolute():
            candidate = Path(self._inner.cwd) / candidate
        return Path(os.path.abspath(candidate))

    def _resolve_outside(self, file_path: str) -> Path | None:
        """Return the resolved path if it escapes all allowed roots."""
        resolved = self._resolve_path(file_path)
        for root in self._allowed_roots:
            if resolved.is_relative_to(root):
                return None
        return resolved

    def _protects_declared_path(
        self,
        resolved: Path,
        *,
        alias: Path | None = None,
        recursive: bool = False,
    ) -> bool:
        if resolved in self._protected_files or any(
            resolved.is_relative_to(root) for root in self._protected_directories
        ):
            return True
        if alias is not None and (
            alias in self._protected_file_aliases
            or any(
                alias.is_relative_to(root)
                for root in self._protected_directory_aliases
            )
        ):
            return True
        if not recursive:
            return False
        return (
            any(path.is_relative_to(resolved) for path in self._protected_files)
            or any(path.is_relative_to(resolved) for path in self._protected_directories)
            or (
                alias is not None
                and (
                    any(
                        path.is_relative_to(alias)
                        for path in self._protected_file_aliases
                    )
                    or any(
                        path.is_relative_to(alias)
                        for path in self._protected_directory_aliases
                    )
                )
            )
        )

    def _reject_protected(self, op: str, file_path: str) -> str:
        logger.warning(
            "AutoBuild declared-path protection: rejected %s of '%s'",
            op,
            file_path,
        )
        return (
            f"Error: refusing to {op} '{file_path}': the project declares "
            "this path as protected evidence and the agent cannot change it."
        )

    def _reject(self, op: str, file_path: str, resolved: Path) -> str:
        logger.warning(
            "AutoBuild write confinement: rejected %s to '%s' — resolves to "
            "'%s', outside allowed roots %s (TASK-FIX-WTESCAPE01)",
            op,
            file_path,
            resolved,
            [str(r) for r in self._allowed_roots],
        )
        message = (
            f"Error: refusing to {op} '{file_path}': it resolves to "
            f"'{resolved}', outside the worktree. All file writes must stay "
            f"inside the worktree root '{self._allowed_roots[0]}'. Retry "
            f"with a worktree-relative path."
        )
        if self._scratch_root is not None:
            message += (
                f" For throwaway scripts and other files you will not keep, "
                f"use the scratch folder '{self._scratch_root}'."
            )
        return message

    # -- write ------------------------------------------------------------
    def write(self, file_path: str, content: str) -> Any:
        escaped = self._resolve_outside(file_path)
        if escaped is not None:
            return WriteResult(error=self._reject("write", file_path, escaped))
        if self._protects_declared_path(
            self._resolve_path(file_path), alias=self._absolute_path(file_path)
        ):
            return WriteResult(error=self._reject_protected("overwrite", file_path))
        return self._inner.write(file_path, content)

    async def awrite(self, file_path: str, content: str) -> Any:
        escaped = self._resolve_outside(file_path)
        if escaped is not None:
            return WriteResult(error=self._reject("write", file_path, escaped))
        if self._protects_declared_path(
            self._resolve_path(file_path), alias=self._absolute_path(file_path)
        ):
            return WriteResult(error=self._reject_protected("overwrite", file_path))
        return await self._inner.awrite(file_path, content)

    # -- edit -------------------------------------------------------------
    def edit(self, file_path: str, *args: Any, **kwargs: Any) -> Any:
        escaped = self._resolve_outside(file_path)
        if escaped is not None:
            return EditResult(error=self._reject("edit", file_path, escaped))
        if self._protects_declared_path(
            self._resolve_path(file_path), alias=self._absolute_path(file_path)
        ):
            return EditResult(error=self._reject_protected("edit", file_path))
        return self._inner.edit(file_path, *args, **kwargs)

    async def aedit(self, file_path: str, *args: Any, **kwargs: Any) -> Any:
        escaped = self._resolve_outside(file_path)
        if escaped is not None:
            return EditResult(error=self._reject("edit", file_path, escaped))
        if self._protects_declared_path(
            self._resolve_path(file_path), alias=self._absolute_path(file_path)
        ):
            return EditResult(error=self._reject_protected("edit", file_path))
        return await self._inner.aedit(file_path, *args, **kwargs)

    # -- grep (explicit for SDK signature inspection) --------------------
    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
        context_lines: int = 0,
    ) -> Any:
        return self._inner.grep(
            pattern,
            path=path,
            glob=glob,
            max_count=max_count,
            context_lines=context_lines,
        )

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
        context_lines: int = 0,
    ) -> Any:
        return await self._inner.agrep(
            pattern,
            path=path,
            glob=glob,
            max_count=max_count,
            context_lines=context_lines,
        )

    # -- delete -----------------------------------------------------------
    def delete(self, file_path: str) -> Any:
        try:
            escaped = self._resolve_outside(file_path)
            resolved = self._resolve_path(file_path) if escaped is None else escaped
        except (OSError, RuntimeError) as exc:
            # Unresolvable paths (including symlink cycles) must fail closed
            # with a tool error so the agent can recover on its next turn.
            return DeleteResult(error=f"Error: cannot resolve '{file_path}' for deletion: {exc}")
        if escaped is not None:
            return DeleteResult(error=self._reject("delete", file_path, escaped))
        if resolved in self._allowed_roots:
            return DeleteResult(
                error=f"Error: refusing to delete allowed root '{resolved}'."
            )
        if self._protects_declared_path(
            resolved, alias=self._absolute_path(file_path), recursive=True
        ):
            return DeleteResult(error=self._reject_protected("delete", file_path))
        return self._inner.delete(file_path)

    async def adelete(self, file_path: str) -> Any:
        try:
            escaped = self._resolve_outside(file_path)
            resolved = self._resolve_path(file_path) if escaped is None else escaped
        except (OSError, RuntimeError) as exc:
            # Unresolvable paths (including symlink cycles) must fail closed
            # with a tool error so the agent can recover on its next turn.
            return DeleteResult(error=f"Error: cannot resolve '{file_path}' for deletion: {exc}")
        if escaped is not None:
            return DeleteResult(error=self._reject("delete", file_path, escaped))
        if resolved in self._allowed_roots:
            return DeleteResult(
                error=f"Error: refusing to delete allowed root '{resolved}'."
            )
        if self._protects_declared_path(
            resolved, alias=self._absolute_path(file_path), recursive=True
        ):
            return DeleteResult(error=self._reject_protected("delete", file_path))
        return await self._inner.adelete(file_path)

    # -- execute (unconfined passthrough) ----------------------------------
    # Defined explicitly (not via ``__getattr__``) because
    # ``deepagents.backends.composite.execute_accepts_timeout`` introspects
    # ``type(default).execute`` at the CLASS level — an AttributeError there
    # is not caught. The ``timeout`` kwarg must appear in the signature so
    # per-call timeout overrides keep flowing through to LocalShellBackend.
    def execute(self, command: str, *, timeout: int | None = None) -> Any:
        return self._inner.execute(command, timeout=timeout)

    async def aexecute(self, command: str, *, timeout: int | None = None) -> Any:
        return await self._inner.aexecute(command, timeout=timeout)


# See the TruncatingBackend registration note above — same ABC gate.
SandboxBackendProtocol.register(PathConfinedBackend)


_NO_EXECUTION_ATTRIBUTES = frozenset({"execute", "aexecute"})


class ReadOnlyBackend:
    """Delegating backend wrapper that refuses every change and every command.

    13 October 2026 (proof defect 5). The second line of defence for a
    read-only request: the harness already binds only the read and search
    tools to the model, and this wrapper makes the backend itself refuse
    anything else. ``write``, ``edit`` and ``delete`` (sync and async) return
    the same kind of tool error the write fence returns, so the model can
    read why. ``upload_files`` (sync and async) writes nothing and answers
    each file with the same readable error. ``execute`` is neither defined
    here nor forwarded through ``__getattr__``, and the class is deliberately NOT registered with
    ``SandboxBackendProtocol``, so ``supports_execution`` is False and a
    reachable ``execute`` answers "Execution not available".

    Reads, ``ls``, ``glob``, ``grep`` and downloads pass through unchanged.
    """

    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> Any:
        if name in _NO_EXECUTION_ATTRIBUTES:
            raise AttributeError(
                f"{type(self).__name__} offers no command execution ({name})"
            )
        return getattr(self._inner, name)

    @staticmethod
    def _refusal(op: str, file_path: str) -> str:
        return (
            f"Error: cannot {op} '{file_path}': this agent is read-only. "
            "It may read and search files but not change them."
        )

    def write(self, file_path: str, content: str) -> Any:
        return WriteResult(error=self._refusal("write", file_path))

    async def awrite(self, file_path: str, content: str) -> Any:
        return WriteResult(error=self._refusal("write", file_path))

    def edit(self, file_path: str, *args: Any, **kwargs: Any) -> Any:
        return EditResult(error=self._refusal("edit", file_path))

    async def aedit(self, file_path: str, *args: Any, **kwargs: Any) -> Any:
        return EditResult(error=self._refusal("edit", file_path))

    def delete(self, file_path: str) -> Any:
        return DeleteResult(error=self._refusal("delete", file_path))

    async def adelete(self, file_path: str) -> Any:
        return DeleteResult(error=self._refusal("delete", file_path))

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[Any]:
        return [
            FileUploadResponse(path=path, error=self._refusal("upload", path))
            for path, _content in files
        ]

    async def aupload_files(self, files: list[tuple[str, bytes]]) -> list[Any]:
        return self.upload_files(files)

    # Explicit for the SDK's class-level ``max_count`` signature inspection,
    # as on PathConfinedBackend.
    def grep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
        context_lines: int = 0,
    ) -> Any:
        return self._inner.grep(
            pattern,
            path=path,
            glob=glob,
            max_count=max_count,
            context_lines=context_lines,
        )

    async def agrep(
        self,
        pattern: str,
        path: str | None = None,
        glob: str | None = None,
        *,
        max_count: int | None = None,
        context_lines: int = 0,
    ) -> Any:
        return await self._inner.agrep(
            pattern,
            path=path,
            glob=glob,
            max_count=max_count,
            context_lines=context_lines,
        )


def _allowed_write_roots(
    worktree: Path,
    extra_write_roots: Sequence[Path | str] | None,
) -> list[Path]:
    """Compute the allowed write roots for a worktree (TASK-FIX-WTESCAPE01).

    Policy (AC-002, explicit by design):

    1. The worktree itself (resolved).
    2. The resolved target of a sibling symlink **literally named**
       ``guardkitfactory`` in the worktree's parent directory. GuardKit's
       worktree layout keeps feature worktrees and an intentional
       ``guardkitfactory -> <host guardkitfactory checkout>`` symlink side
       by side under ``.guardkit/worktrees/``; cross-repo tasks
       (TASK-AB-XREPOEV01 lineage) legitimately write through it. Any
       *other* symlink escape is rejected.
    3. Caller-supplied ``extra_write_roots``, resolved.
    """
    roots = [worktree.resolve()]
    factory_symlink = worktree.parent / "guardkitfactory"
    if factory_symlink.is_symlink():
        resolved_target = factory_symlink.resolve()
        if resolved_target.is_dir():
            roots.append(resolved_target)
    for extra in extra_write_roots or []:
        roots.append(Path(extra).resolve())
    return roots


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


def _ensure_private_directory(directory: Path, label: str) -> Path:
    """Create ``directory`` (mode 0700) or reuse it; refuse anything else.

    An existing folder must belong to this process's user and is set to mode
    0700 if it is not already (19 October 2026, through
    :func:`ensure_owner_only_directory`); a symlink, a non-folder or another
    user's folder is refused with ``ValueError``.

    Two backends built at once for one new worktree may both find it missing;
    the one that loses the ``mkdir`` race reuses the folder the other made
    (14 October 2026), still subject to the checks below.
    """
    try:
        status = directory.lstat()
    except FileNotFoundError:
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            pass
        except OSError as exc:
            raise ValueError(
                f"AutoBuild {label} could not be created at {directory}"
            ) from exc
        try:
            status = directory.lstat()
        except OSError as exc:
            raise ValueError(
                f"AutoBuild {label} could not be inspected at {directory}"
            ) from exc
    except OSError as exc:
        raise ValueError(
            f"AutoBuild {label} could not be inspected at {directory}"
        ) from exc

    if stat.S_ISLNK(status.st_mode):
        raise ValueError(f"AutoBuild {label} must not be a symlink: {directory}")
    if not stat.S_ISDIR(status.st_mode):
        raise ValueError(f"AutoBuild {label} must be a directory: {directory}")
    # 19 October 2026: an existing folder is not taken as it is. It must be
    # this user's, and it is made owner-only, as a new one would be.
    return ensure_owner_only_directory(directory, label)


def ensure_owner_only_directory(directory: Path, label: str) -> Path:
    """Make an existing ``directory`` readable by its owner alone, or refuse.

    14 October 2026: for the folders holding the coding model's transcripts.
    The folder is opened without following a symlink, must belong to this
    process's user, and is set to mode 0700 if it is not already. Anything
    else (a symlink, not a directory, another owner, a failed change) raises
    ``ValueError``.
    """
    try:
        descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise ValueError(
            f"AutoBuild {label} is not a real folder that can be opened: {directory}"
        ) from exc
    try:
        status = os.fstat(descriptor)
        if status.st_uid != os.geteuid():
            raise ValueError(
                f"AutoBuild {label} belongs to another user: {directory}"
            )
        if stat.S_IMODE(status.st_mode) != 0o700:
            os.fchmod(descriptor, 0o700)
            if stat.S_IMODE(os.fstat(descriptor).st_mode) != 0o700:
                raise ValueError(
                    f"AutoBuild {label} could not be made private: {directory}"
                )
    except OSError as exc:
        raise ValueError(
            f"AutoBuild {label} could not be made private: {directory}"
        ) from exc
    finally:
        os.close(descriptor)
    return directory


def _private_artifacts_folder(directory: Path, label: str) -> Path:
    """Create or reuse ``directory``, then make it owner-only."""
    return ensure_owner_only_directory(
        _ensure_private_directory(directory, label), label
    )


# 14 October 2026: the coding model's own working files. deepagents writes
# them under ``<artifacts_root>/<name>/``.
MODEL_ARTIFACT_NAMES = ("conversation_history", "large_tool_results")
# Their folder, inside GuardKit's builder scratch folder.
_MODEL_ARTIFACTS_SUBDIR = "model-artifacts"
# The temporary folders each non-git worktree was given in this process, one
# per use (the model's working files, the shell's home folder), so every
# backend for it (and the paths quoted to the model) stays the same.
_temporary_model_artifacts: dict[tuple[str, Path], Path] = {}
_temporary_model_artifacts_lock = threading.Lock()


def _remove_temporary_model_artifacts() -> None:
    """At process exit, remove the temporary folders (best effort)."""
    with _temporary_model_artifacts_lock:
        folders = list(_temporary_model_artifacts.values())
        _temporary_model_artifacts.clear()
    for folder in folders:
        shutil.rmtree(folder, ignore_errors=True)


def _temporary_private_folder(use: str, project: Path, description: str) -> Path:
    """The private temporary folder for ``use`` and ``project`` in this process.

    For a worktree GuardKit has no scratch folder for. Made on first need,
    the same one afterwards, removed when the process exits; a warning names
    it once.
    """
    with _temporary_model_artifacts_lock:
        folder = _temporary_model_artifacts.get((use, project))
        if folder is None or folder.is_symlink() or not folder.is_dir():
            if not _temporary_model_artifacts:
                atexit.register(_remove_temporary_model_artifacts)
            folder = Path(tempfile.mkdtemp(prefix=f"guardkit-{use}-")).resolve()
            _temporary_model_artifacts[(use, project)] = folder
            logger.warning(
                "AutoBuild worktree %s has no git folder for %s; they go to "
                "the private temporary folder %s instead.",
                project,
                description,
                folder,
            )
    return folder


def model_artifacts_root(worktree: Path) -> Path:
    """Return the private folder for the coding model's own working files.

    14 October 2026. deepagents writes ``conversation_history/<thread>.md``
    (a summarised transcript, which quotes every path the model saw) and
    ``large_tool_results/<id>`` (tool output too big to keep inline) under
    the backend's ``artifacts_root``. That root was the worktree, so
    GuardKit's checkpoint commit took them into the build's branch: build
    FEAT-7F1D committed a 216 KB transcript to a public project.

    They now go to ``model-artifacts/`` in GuardKit's builder scratch folder
    (``guardkit.orchestrator.paths.prepare_builder_scratch_dir``), which sits
    in the worktree's own git directory: git never stages it, ``git worktree
    remove`` deletes it with the worktree, and every backend built for one
    worktree gets the same folder.

    When GuardKit has no safe scratch folder for the worktree (it is not a
    git checkout, or ``guardkit-scratch`` is a symlink, not a folder, inside
    the project or cannot be made), ``prepare_builder_scratch_dir`` returns
    ``None`` and a private temporary folder is used instead, with a warning:
    the same one for that worktree for the rest of the process, removed when
    the process exits.

    Every time, the folder is made owner-only (mode 0700, owned by this
    user) and returned resolved. ``model-artifacts`` itself being a symlink,
    not a folder, another user's or impossible to make private, or a folder
    inside the project, refuses construction with ``ValueError``.
    """
    try:
        from guardkit.orchestrator.paths import prepare_builder_scratch_dir
    except ImportError as exc:  # pragma: no cover - GuardKit is a run-time need
        raise RuntimeError(
            "The AutoBuild backend needs GuardKit's builder scratch folder and "
            f"GuardKit cannot be imported ({exc}); the backend is not built."
        ) from exc

    worktree = Path(worktree)
    project = worktree.resolve()
    scratch = prepare_builder_scratch_dir(worktree)
    if scratch is None:
        folder = _temporary_private_folder(
            "model-artifacts",
            project,
            "the coding model's own working files (conversation summaries and "
            "large tool output)",
        )
        folder = ensure_owner_only_directory(folder, "model artifacts folder")
    else:
        folder = _private_artifacts_folder(
            Path(scratch) / _MODEL_ARTIFACTS_SUBDIR, "model artifacts folder"
        ).resolve()
    if folder.is_relative_to(project) and not folder.is_relative_to(project / ".git"):
        raise ValueError(f"AutoBuild model artifacts folder is inside the project: {folder}")
    return folder


# 12 October 2026: the project's declared ``launch:`` names for the shell.
_LAUNCH_KEYS = frozenset({"settings", "scratch"})
# Scratch entries live here, under the scratch folder.
_LAUNCH_SCRATCH_SUBDIR = "toolchain"
# The name rules, mirrored from Forge's ``launch_environment``
# (``declared_setting_refusal``) and GuardKit's ``launch_declaration``; keep
# the three in step. (Corrected 13 October 2026: this package does need
# GuardKit at run time — ``harness/langgraph_harness.py`` imports it, and
# :func:`build_autobuild_backend` passes the shell's environment through
# GuardKit's ``finish_project_environment``. It never imports Forge.)
_LAUNCH_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_LAUNCH_MAX_NAME_LENGTH = 128
_LAUNCH_RESERVED_PREFIXES = ("FORGE_", "GUARDKIT_", "FLEET_MEMORY_", "OPENAI_", "ANTHROPIC_")
_LAUNCH_RESERVED_NAMES = frozenset({"PATH", "HOME", "TMPDIR", "SSH_AUTH_SOCK"})
_LAUNCH_CREDENTIAL_WORDS = (
    "TOKEN",
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "API_KEY",
    "APIKEY",
    "CREDENTIAL",
    "PRIVATE_KEY",
)


def _launch_name_refusal(name: object) -> str | None:
    """``None`` for a name a project may declare, else why not."""
    # fullmatch: ``$`` in a ``match`` would also accept a trailing newline.
    if not isinstance(name, str) or not _LAUNCH_NAME_RE.fullmatch(name):
        return "is not a variable name"
    if len(name) > _LAUNCH_MAX_NAME_LENGTH:
        return f"is longer than {_LAUNCH_MAX_NAME_LENGTH} characters"
    upper = name.upper()
    if upper.startswith(_LAUNCH_RESERVED_PREFIXES) or upper in _LAUNCH_RESERVED_NAMES:
        return "is reserved for the factory itself"
    if any(word in upper for word in _LAUNCH_CREDENTIAL_WORDS):
        return "is credential-shaped"
    return None


def _launch_names(
    launch_environment: Mapping[str, Sequence[str]] | None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Return ``(settings, scratch)`` names, refusing anything malformed.

    GuardKit validates the project's declaration first; this is the second
    check, at the point the names reach the shell.
    """
    if not launch_environment:
        return (), ()
    unknown = sorted(set(launch_environment) - _LAUNCH_KEYS)
    if unknown:
        raise ValueError(f"AutoBuild launch environment has unknown keys: {unknown}")
    lists = []
    for key in ("settings", "scratch"):
        raw = launch_environment.get(key)
        if raw is None:
            raw = ()
        if not isinstance(raw, (list, tuple)):
            # A string would otherwise be read letter by letter.
            raise ValueError(
                f"AutoBuild launch {key} must be a list of names, "
                f"not {type(raw).__name__}"
            )
        names = tuple(raw)
        for name in names:
            refusal = _launch_name_refusal(name)
            if refusal is not None:
                raise ValueError(f"AutoBuild launch {key} name {name!r} {refusal}")
        lists.append(names)
    return lists[0], lists[1]


def _no_launch_scratch_folder(scratch: Sequence[str]) -> str:
    return (
        "The project declares launch scratch folders "
        f"({', '.join(scratch)}) but this shell has no scratch folder, so it "
        "cannot be built. Nothing is put inside the project instead."
    )


def _apply_launch_environment(
    env: dict[str, str],
    settings: Sequence[str],
    scratch: Sequence[str],
    scratch_root: Path | None,
) -> None:
    """Add the declared settings and scratch folders to the shell's ``env``.

    A name never replaces one this module sets itself. A declared setting is
    copied from this process's environment only when set there. Each scratch
    name is set to ``<scratch_root>/toolchain/<NAME>``, a private folder made
    on demand; with no scratch folder construction fails, because the only
    other place a tool's cache could go is inside the project.
    """
    own = set(env) | {"PYTHONPATH"}
    for name in settings:
        if name in own:
            logger.warning(
                "AutoBuild launch setting %s is set by the backend itself; "
                "the declared value is not passed.",
                name,
            )
            continue
        value = os.environ.get(name)
        if value is not None:
            env[name] = value
    if not scratch:
        return
    clashing = sorted(set(scratch) & own)
    if clashing:
        raise ValueError(
            f"AutoBuild launch scratch names are set by the backend itself: {clashing}"
        )
    if scratch_root is None:
        raise ValueError(_no_launch_scratch_folder(scratch))
    base = _ensure_private_directory(
        scratch_root / _LAUNCH_SCRATCH_SUBDIR, "launch scratch folder"
    )
    for name in scratch:
        env[name] = str(_ensure_private_directory(base / name, "launch scratch folder"))


def _shell_toolchain_folder(
    worktree: Path, name: str, label: str, description: str
) -> Path:
    """Return the shell's private ``<scratch>/toolchain/<name>`` folder.

    The scratch folder is GuardKit's builder scratch folder
    (``guardkit.orchestrator.paths.prepare_builder_scratch_dir``), inside the
    worktree's own git directory: git never stages it and ``git worktree
    remove`` deletes it with the worktree. ``name`` is never one of the
    folders GuardKit's own project commands use (``toolchain/HOME`` and
    ``toolchain/TMPDIR``, ``guardkit.orchestrator.project_command_env``):
    those commands run the checks the build is judged by, and a file the
    builder's shell leaves in its home folder (a ``.pth`` file under
    ``~/.local``, a ``~/.npmrc``, a ``~/.gitconfig``) must not change what
    they run while ``git status`` stays empty. ``name`` has a hyphen, so no
    declared ``launch.scratch`` name can be the same folder.

    An existing real folder is reused as it is; a missing one is made with
    mode 0700. A symlink (broken or not) or a non-folder refuses construction
    with ``ValueError``, as does a folder inside the project (other than under
    its own ``.git``). When GuardKit has no scratch folder for the worktree
    (it is not a git checkout), a private temporary folder is used instead,
    with a warning, the same one for that worktree for the rest of the process
    and removed when the process exits. Returned resolved.
    """
    try:
        from guardkit.orchestrator.paths import prepare_builder_scratch_dir
    except ImportError as exc:  # pragma: no cover - GuardKit is a run-time need
        raise RuntimeError(
            "The AutoBuild shell needs GuardKit's builder scratch folder for "
            f"its {description} and GuardKit cannot be imported ({exc}); the "
            "shell is not built."
        ) from exc

    worktree = Path(worktree)
    project = worktree.resolve()
    scratch = prepare_builder_scratch_dir(worktree)
    if scratch is None:
        folder = _temporary_private_folder(
            name.lower(), project, f"the shell's {description}"
        )
    else:
        base = _ensure_private_directory(Path(scratch) / _LAUNCH_SCRATCH_SUBDIR, label)
        folder = _ensure_private_directory(base / name, label)
    folder = folder.resolve()
    if folder.is_relative_to(project) and not folder.is_relative_to(project / ".git"):
        raise ValueError(f"AutoBuild {label} is inside the project: {folder}")
    return folder


def shell_home(worktree: Path) -> Path:
    """Return the private ``HOME`` for every shell built for ``worktree``.

    19 October 2026 (build FEAT-B874). The shell's ``HOME`` was the worktree,
    so every tool that keeps a cache or settings under the home folder wrote
    them into the project: one ``npm install`` by the builder put 2,058 files
    of ``.npm/_cacache`` into the build's worktree. The same holds for pip's,
    Cargo's, Go's and any other tool's default caches, which all follow
    ``HOME``. So ``HOME`` is now ``<scratch>/toolchain/SHELL-HOME``
    (:func:`_shell_toolchain_folder`), shared by the builder's and the
    checker's shells and kept apart from the project commands' ``HOME`` (so
    the two do not share caches; accepted). No tool is named and no project
    declaration is needed; a declared ``launch.scratch`` name still points
    its own tool elsewhere.
    """
    return _shell_toolchain_folder(
        worktree, "SHELL-HOME", "shell home folder", "home folder (tool caches)"
    )


def shell_tmpdir(worktree: Path) -> Path:
    """Return the private ``TMPDIR`` for every shell built for ``worktree``.

    19 October 2026. ``TMPDIR`` was ``<worktree>/.tmp``, so every temporary
    file a tool made (Node's compile cache among them) landed in the project,
    kept out of commits only by GuardKit's ``.tmp/`` filters. It is now
    ``<scratch>/toolchain/SHELL-TMPDIR`` (:func:`_shell_toolchain_folder`),
    apart from the project commands' ``TMPDIR``. Errors name ``TMPDIR``.
    """
    return _shell_toolchain_folder(
        worktree, "SHELL-TMPDIR", "TMPDIR", "temporary folder"
    )


def _finish_shell_environment(
    env: dict[str, str], scratch_names: Sequence[str]
) -> dict[str, str]:
    """GuardKit's last steps for a project command's environment.

    13 October 2026 (design ``factory-project-commands-without-factory-
    credentials``, section 1b): the shell keeps its own base (``PATH``,
    ``HOME`` and ``TMPDIR`` in the scratch folder (:func:`shell_home`,
    :func:`shell_tmpdir`), the Python flags, the declared
    settings and scratch folders), then GuardKit's
    ``finish_project_environment`` checks every proxy setting for a user
    name or password (a declared ``HTTPS_PROXY`` or ``https_proxy`` that
    carries one refuses construction, naming the setting and never its value)
    and applies the run-owner marker last, from this process alone, so a
    server the builder starts in a new session is still found when the build
    is cancelled.

    If GuardKit cannot be imported, construction is refused rather than
    falling back.
    """
    try:
        from guardkit.orchestrator.project_command_env import (
            finish_project_environment,
        )
    except ImportError as exc:  # pragma: no cover - GuardKit is a run-time need
        raise RuntimeError(
            "The AutoBuild shell needs GuardKit's project-command environment "
            f"and GuardKit cannot be imported ({exc}); the shell is not built."
        ) from exc
    return finish_project_environment(env, scratch_names=tuple(scratch_names))


def build_autobuild_backend(
    worktree: Path,
    *,
    max_tool_result_chars: int | None = None,
    extra_write_roots: Sequence[Path | str] | None = None,
    protected_paths: Sequence[Path | str] = (),
    scratch_root: Path | str | None = None,
    launch_environment: Mapping[str, Sequence[str]] | None = None,
    launch_scratch_root: Path | str | None = None,
    read_only: bool = False,
) -> CompositeBackend:
    """Construct the AutoBuild backend for a given worktree (AC-001/002).

    Returns a :class:`CompositeBackend` whose ``default`` is the configured
    :class:`LocalShellBackend` and whose ``artifacts_root`` is the private
    folder from :func:`model_artifacts_root`, outside the project. The
    composite's only routes send ``<artifacts_root>/conversation_history/``
    and ``<artifacts_root>/large_tool_results/`` to that folder (none for a
    read-only backend); every other operation falls through to the
    underlying ``LocalShellBackend``. The reason for the wrapper is to expose
    ``artifacts_root`` to deepagents' summarisation middleware so the SDK's
    hard-coded ``/conversation_history`` offload prefix is re-rooted at a
    real, writable folder rather than at host root
    (TASK-HMIG-002R-SUMM-ROOT; moved out of the worktree on 14 October 2026,
    see module docstring).

    The underlying ``LocalShellBackend`` is configured per the AC-002
    contract, as amended by TASK-HMIG-002R-NOVMODE (2026-06-03):

    * ``root_dir=worktree`` — the agent's filesystem root
    * ``virtual_mode=False`` — absolute paths resolve literally (was
      ``True``; flipped after AC-001D run 5 — see module docstring)
    * ``env`` — minimal explicit environment (``PATH``; ``HOME`` and
      ``TMPDIR`` in the private folders from :func:`shell_home` and
      :func:`shell_tmpdir`, outside the project; Python
      no-bytecode/no-user-site flags; and ``PYTHONPATH`` if a ``.venv`` is
      detected)
    * ``inherit_env=False`` — no leakage from the operator's shell
    * ``timeout=600`` — 10-minute ``execute`` ceiling
    * ``max_output_bytes=1_000_000`` — 1 MB cap on ``execute`` output

    Tests and other consumers that need the underlying ``LocalShellBackend``
    (e.g. to assert ``virtual_mode`` / ``_env`` / ``_default_timeout``) can
    reach it via ``backend.default`` — the :class:`PathConfinedBackend`
    (and optional :class:`TruncatingBackend`) wrappers delegate unknown
    attributes to the inner backend, so ``backend.default.virtual_mode``
    etc. resolve transparently.

    The companion :func:`guardkitfactory.harness.permissions.build_autobuild_permissions`
    factory returns the deny-rule list that should be passed alongside this
    backend to :class:`guardkitfactory.harness.LangGraphHarness`.

    Args:
        worktree: Filesystem path to the worktree the agent should operate
            inside. It must exist before construction. The shell's private
            ``HOME`` and ``TMPDIR`` are made outside it (:func:`shell_home`,
            :func:`shell_tmpdir`); a symlink, non-directory or creation
            failure there refuses construction before exposing shell
            execution.
        max_tool_result_chars: TASK-PERF-COACHSYNTH. When set, each
            ``read``/``grep``/``execute`` result is capped at this many chars
            (with a visible truncation marker) via :class:`TruncatingBackend`,
            bounding how much a single tool cycle can add to the agent's
            running context. ``None`` (the default) leaves results uncapped —
            the Player and synthesis paths pass ``None``; only the Coach
            B-full gather passes a limit so its tool-using loop cannot
            overflow the model window (the run-22 TP05 F20 surface).
        extra_write_roots: TASK-FIX-WTESCAPE01. Additional directories
            (beyond the worktree and the intentional ``guardkitfactory``
            sibling symlink — see :func:`_allowed_write_roots`) that
            ``write``/``edit`` may target. ``None`` (the default) confines
            writes to the worktree + sibling-symlink policy roots.
        protected_paths: Existing project-declared files or directories that
            the Player may read but may not write, edit, or delete. Relative
            paths resolve from ``worktree``. Missing, escaping, or invalid
            declarations fail construction instead of weakening protection.
        scratch_root: 3 October 2026. A folder outside the project where the
            builder may write throwaway scripts (guardkit passes one inside
            the worktree's git directory). It is created if missing, added to
            the allowed write roots, and named in every refusal. A symlink, a
            non-directory, a folder inside the project (other than under the
            worktree's own ``.git``) or one that cannot be created is skipped
            with a warning; ``backend.default.scratch_root`` then reads
            ``None``. ``None`` keeps the earlier behaviour.
        launch_environment: 12 October 2026. The names the project declares
            in its ``launch:`` block, as ``{"settings": [...], "scratch":
            [...]}``. Each setting is copied from this process's environment
            when set there; each scratch name is set to
            ``<scratch_root>/toolchain/<NAME>``, created private on demand.
            Declared scratch names with no usable ``scratch_root`` fail
            construction (no fallback into the worktree).
            ``None`` keeps the environment exactly as before.
        launch_scratch_root: The folder declared scratch names resolve under
            when this shell has no ``scratch_root`` of its own (guardkit passes
            the worktree's scratch folder for the Coach and specialists). Held
            to the same checks as ``scratch_root``, failing construction when
            refused, but NOT added to the allowed write roots: the caches are
            written by shell commands, which write confinement does not cover,
            so the file tools gain no write access.
        read_only: 13 October 2026. When True, the backend is wrapped in a
            :class:`ReadOnlyBackend`: write, edit and delete come back as tool
            errors and no command can be run (``supports_execution`` is
            False). The caller asks for this when the agent's tool request is
            read-only; it backs up the harness's own tool allowlist. False
            (the default) keeps the backend exactly as before.

    Returns:
        A configured :class:`CompositeBackend` wrapping a
        :class:`LocalShellBackend` (optionally behind a
        :class:`TruncatingBackend`), ready to be passed to
        :class:`guardkitfactory.harness.LangGraphHarness`.
    """
    worktree = Path(worktree)
    launch_settings, launch_scratch = _launch_names(launch_environment)
    if launch_scratch and scratch_root is None and launch_scratch_root is None:
        # Refused before anything is created in the worktree.
        raise ValueError(_no_launch_scratch_folder(launch_scratch))
    if not worktree.is_dir():
        raise ValueError(f"AutoBuild worktree is not an existing folder: {worktree}")
    # Outside the project, so no temporary file lands in it (19 October 2026).
    temp_directory = shell_tmpdir(worktree)
    project = worktree.resolve()

    def inside_project(path: Path) -> bool:
        return path.is_relative_to(project) and not path.is_relative_to(
            project / ".git"
        )

    def checked_scratch_folder(planned: Path) -> Path:
        # Judged before and after creation, so nothing lands in the project.
        if inside_project(planned.parent.resolve() / planned.name):
            raise ValueError(
                f"AutoBuild scratch folder is inside the project: {planned}"
            )
        folder = _ensure_private_directory(planned, "scratch folder").resolve()
        if inside_project(folder):
            raise ValueError(
                f"AutoBuild scratch folder is inside the project: {folder}"
            )
        return folder

    if scratch_root is not None:
        try:
            scratch_root = checked_scratch_folder(Path(scratch_root))
        except ValueError as exc:
            # A convenience, not a safeguard: without it the build still runs
            # and a scratch write is refused like any other outside write.
            # Not so when the project's declared caches need it.
            if launch_scratch:
                raise
            logger.warning("%s; continuing without a scratch folder.", exc)
            scratch_root = None
        else:
            extra_write_roots = [*(extra_write_roots or []), scratch_root]
    # Where declared scratch names resolve: the shell's own scratch folder,
    # else the one handed over for that alone (never a write root).
    launch_base = scratch_root
    if launch_base is None and launch_scratch and launch_scratch_root is not None:
        launch_base = checked_scratch_folder(Path(launch_scratch_root))

    env: dict[str, str] = {
        "PATH": _AUTOBUILD_PATH,
        # Outside the project, so no tool's cache lands in it (19 October 2026).
        "HOME": str(shell_home(worktree)),
        "TMPDIR": str(temp_directory),
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
    }
    venv_site_packages = _detect_venv_site_packages(worktree)
    if venv_site_packages is not None:
        env["PYTHONPATH"] = venv_site_packages
    if launch_environment is not None:
        _apply_launch_environment(
            env, launch_settings, launch_scratch, launch_base
        )
    env = _finish_shell_environment(env, launch_scratch)

    local_shell = LocalShellBackend(
        root_dir=worktree,
        virtual_mode=False,  # TASK-HMIG-002R-NOVMODE — see module docstring
        env=env,
        inherit_env=False,
        timeout=_AUTOBUILD_EXECUTE_TIMEOUT_SECONDS,
        max_output_bytes=_AUTOBUILD_EXECUTE_MAX_OUTPUT_BYTES,
    )

    # TASK-FIX-WTESCAPE01 — confine write/edit/delete to the allowed roots. This
    # restores the file-tool containment NOVMODE removed, without touching
    # the literal-absolute-path semantics for in-worktree paths (Coach JSON
    # writes still work).
    default_backend: Any = PathConfinedBackend(
        local_shell,
        _allowed_write_roots(worktree, extra_write_roots),
        protected_paths=protected_paths,
        scratch_root=scratch_root,
    )

    # TASK-PERF-COACHSYNTH — optionally cap per-tool-result size for the
    # Coach gather. The TruncatingBackend overrides only read/grep/execute,
    # disjoint from PathConfinedBackend's mutation overrides, so stacking
    # order is immaterial for behaviour; confinement sits innermost so it
    # also guards any future wrapper that delegates writes. ``None`` leaves
    # results uncapped (Player/synthesis behaviour unchanged).
    if max_tool_result_chars is not None:
        default_backend = TruncatingBackend(default_backend, max_tool_result_chars)

    # 13 October 2026 (proof defect 5): outermost, so nothing underneath can
    # re-offer writes or execution.
    if read_only:
        default_backend = ReadOnlyBackend(default_backend)

    # TASK-HMIG-002R-SUMM-ROOT, moved out of the worktree on 14 October 2026:
    # the middleware's offload prefixes become
    # ``<private folder>/conversation_history`` and ``.../large_tool_results``
    # (see :func:`model_artifacts_root`), never the worktree and never host
    # root. The write fence refuses anything outside the worktree, so each
    # prefix is routed to its own folder; every other path still falls
    # through to the default backend. A read-only backend gets no routes: it
    # refuses those writes as before.
    artifacts_root = model_artifacts_root(worktree)
    routes: dict[str, Any] = {}
    if not read_only:
        for name in MODEL_ARTIFACT_NAMES:
            folder = _private_artifacts_folder(
                artifacts_root / name, "model artifacts folder"
            )
            routes[f"{artifacts_root}/{name}/"] = FilesystemBackend(
                root_dir=folder, virtual_mode=True
            )
    return CompositeBackend(
        default=default_backend,
        routes=routes,
        artifacts_root=str(artifacts_root),
    )
