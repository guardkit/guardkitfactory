"""TASK-CGCP-009 rehydration guard — wired as a regular integration test.

The CI grep guard from
``tests/forge/adapters/test_resume_value_helper.py`` (TASK-CGCP-009) is
the project's defence against risk **R2** — runtime-mode rehydration
drift. Every ``interrupt()`` consumer in ``src/forge/`` MUST funnel its
resume value through :func:`forge.adapters.langgraph.resume_value_as`
before any attribute access. The guard is AST-based so it ignores
docstring / comment mentions of the forbidden patterns.

This module re-runs the guard from inside ``tests/integration/`` so the
integration suite has its own end-to-end sanity check independent of the
unit-test directory layout. If the unit-suite is moved, renamed, or
removed in a future refactor the integration suite still proves the
same invariant on its own.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from forge.adapters.langgraph import resume_value_as

# ---------------------------------------------------------------------------
# Constants pulled verbatim from the canonical guard so the contract is the
# same whether you run the unit-level or integration-level invocation.
# ---------------------------------------------------------------------------


_REHYDRATION_GUARD_ALLOWLIST = "noqa: rehydration-guard"

#: Attributes whose access on an unrehydrated ``interrupt()`` value is
#: a documented silent-regression hazard under server mode.
_FORBIDDEN_ATTRS: frozenset[str] = frozenset({"decision", "responder"})


def _repo_root() -> Path:
    # tests/integration/test_rehydration_guard.py → repo root is two
    # parents up.
    return Path(__file__).resolve().parents[2]


def _iter_forge_python_files() -> list[Path]:
    forge_root = _repo_root() / "src" / "forge"
    return [p for p in forge_root.rglob("*.py") if "__pycache__" not in p.parts]


def _callable_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _scan_function_for_violations(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
) -> list[tuple[int, str]]:
    interrupt_lines: list[int] = []
    helper_lines: list[int] = []
    bad_attrs: list[ast.Attribute] = []

    for node in ast.walk(func):
        if isinstance(node, ast.Call):
            name = _callable_name(node.func)
            if name == "interrupt":
                interrupt_lines.append(node.lineno)
            elif name == "resume_value_as":
                helper_lines.append(node.lineno)
        elif isinstance(node, ast.Attribute):
            if node.attr in _FORBIDDEN_ATTRS:
                bad_attrs.append(node)

    if not interrupt_lines or not bad_attrs:
        return []

    interrupt_lines.sort()
    helper_lines.sort()

    violations: list[tuple[int, str]] = []
    earliest_interrupt = interrupt_lines[0]
    for attr in bad_attrs:
        attr_line = attr.lineno
        if attr_line <= earliest_interrupt:
            continue
        rehydrated = any(
            earliest_interrupt < hl <= attr_line for hl in helper_lines
        )
        if rehydrated:
            continue
        snippet = (
            source_lines[attr_line - 1] if attr_line - 1 < len(source_lines) else ""
        )
        if _REHYDRATION_GUARD_ALLOWLIST in snippet:
            continue
        violations.append((attr_line, snippet.rstrip()))
    return violations


def _scan_file(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return []
    source_lines = text.splitlines()
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(
                _scan_function_for_violations(node, source_lines)
            )
    return violations


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRehydrationGuardCleanInForgeSource:
    """No ``interrupt()`` consumer reads ``.decision`` / ``.responder``
    without first funnelling through :func:`resume_value_as`.
    """

    def test_no_unhelpered_interrupt_attribute_access_in_forge_source(
        self,
    ) -> None:
        offenders: list[str] = []
        for path in _iter_forge_python_files():
            for line_no, snippet in _scan_file(path):
                offenders.append(f"{path}:{line_no}: {snippet}")
        assert not offenders, (
            "DDR-002 regression: interrupt() consumer reads "
            ".decision/.responder without going through resume_value_as. "
            "Offenders:\n" + "\n".join(offenders)
        )


class TestRehydrationScannerSelfCheck:
    """Confidence test: synthetic offending source is detected.

    Runs the scanner against a hand-built file that fakes the
    regression pattern. If the scanner itself silently passes
    everything, this test fails.
    """

    def test_scanner_detects_synthetic_violation(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.py"
        bad.write_text(
            "async def consume():\n"
            "    raw = await interrupt({})\n"
            "    return raw.decision\n",
            encoding="utf-8",
        )
        violations = _scan_file(bad)
        assert violations, "scanner failed to detect synthetic regression"
        line_no, snippet = violations[0]
        assert line_no == 3
        assert ".decision" in snippet

    def test_scanner_respects_allowlist_directive(
        self, tmp_path: Path
    ) -> None:
        allowed = tmp_path / "allowed.py"
        allowed.write_text(
            "async def consume():\n"
            "    raw = await interrupt({})\n"
            "    return raw.decision  # noqa: rehydration-guard\n",
            encoding="utf-8",
        )
        assert _scan_file(allowed) == []

    def test_scanner_accepts_helpered_access(self, tmp_path: Path) -> None:
        ok = tmp_path / "ok.py"
        ok.write_text(
            "async def consume():\n"
            "    raw = await interrupt({})\n"
            "    typed = resume_value_as(object, raw)\n"
            "    return typed.decision\n",
            encoding="utf-8",
        )
        assert _scan_file(ok) == []


class TestResumeValueAsContract:
    """Smoke check that the helper itself round-trips dict input.

    This is a thin integration smoke — the unit-suite owns the
    exhaustive contract tests. The point here is to ensure the helper
    is **importable from the integration suite** and behaves
    consistently with the AST guard's expectation that any code path
    flowing through it has been rehydrated.
    """

    def test_dict_input_is_rehydrated_through_helper(self) -> None:
        from nats_core.events import ApprovalResponsePayload

        raw = {
            "request_id": "rid",
            "decision": "approve",
            "decided_by": "rich",
        }
        typed = resume_value_as(ApprovalResponsePayload, raw)
        assert isinstance(typed, ApprovalResponsePayload)
        assert typed.decision == "approve"
