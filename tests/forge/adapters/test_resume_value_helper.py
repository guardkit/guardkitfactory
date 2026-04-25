"""Tests for the ``resume_value_as`` rehydration helper (TASK-CGCP-009 / DDR-002).

These tests cover the four AC behaviour points plus the CI grep guard:

1. ``isinstance`` short-circuit returns the typed instance unchanged
   (identity check, not just equality) — direct-invoke mode.
2. ``dict`` input round-trips through ``model_validate`` and produces
   an equivalent typed instance — server-mode (``langgraph dev`` /
   LangGraph server).
3. Group D ``Scenario Outline`` parametrised contract test: caller
   code observes a typed :class:`ApprovalResponsePayload` regardless
   of whether the input was a typed instance or a bare mapping of
   equivalent content.
4. Inputs that are neither ``typ`` nor ``dict``-like raise ``TypeError``
   with a clear message.
5. CI grep guard: scans every ``.py`` file under ``src/forge/`` for
   ``interrupt()`` calls whose result is later attribute-accessed via
   ``.decision`` / ``.responder`` without an intervening
   ``resume_value_as`` call. Any match is a regression. The scan is
   AST-based so docstring/comment mentions of those identifiers are
   ignored automatically — only real code paths are inspected.

The grep guard is intentionally implemented inline (not via subprocess)
so the failure surface in CI is a normal pytest assertion with the
offending file/line attached.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from nats_core.events import ApprovalResponsePayload

from forge.adapters.langgraph import resume_value_as


# ---------------------------------------------------------------------------
# Fixtures: representative typed and dict approval payloads.
# ---------------------------------------------------------------------------


_REQUEST_ID = "req-build-FEAT-DEMO-stage-plan-attempt-1"

_TYPED_PAYLOAD_KWARGS = {
    "request_id": _REQUEST_ID,
    "decision": "approve",
    "decided_by": "rich",
    "notes": "looks good",
}


def _typed_payload() -> ApprovalResponsePayload:
    return ApprovalResponsePayload(**_TYPED_PAYLOAD_KWARGS)


def _dict_payload() -> dict[str, str]:
    # Equivalent dict shape — what ``interrupt()`` returns under
    # ``langgraph dev`` server mode (DDR-002 / API §4.2).
    return dict(_TYPED_PAYLOAD_KWARGS)


# ---------------------------------------------------------------------------
# AC: ``isinstance`` short-circuit returns ``raw`` unchanged.
# ---------------------------------------------------------------------------


class TestDirectInvokeShortCircuit:
    """Direct-invoke mode: typed input MUST be returned unchanged."""

    def test_typed_input_is_returned_by_identity(self) -> None:
        # Arrange
        original = _typed_payload()
        # Act
        result = resume_value_as(ApprovalResponsePayload, original)
        # Assert — identity, not just equality (per AC).
        assert result is original

    def test_typed_input_subclass_short_circuits(self) -> None:
        # Subclasses of ``typ`` are also typed and MUST short-circuit.
        class _SubclassPayload(ApprovalResponsePayload):
            pass

        original = _SubclassPayload(**_TYPED_PAYLOAD_KWARGS)
        result = resume_value_as(ApprovalResponsePayload, original)
        assert result is original


# ---------------------------------------------------------------------------
# AC: ``dict`` input round-trips through ``model_validate``.
# ---------------------------------------------------------------------------


class TestServerModeDictRehydration:
    """Server-mode: ``dict`` input is validated into a typed instance."""

    def test_dict_input_is_rehydrated_to_typed_instance(self) -> None:
        # Arrange
        raw = _dict_payload()
        # Act
        result = resume_value_as(ApprovalResponsePayload, raw)
        # Assert — concrete type and field-level equivalence.
        assert isinstance(result, ApprovalResponsePayload)
        assert result.request_id == _REQUEST_ID
        assert result.decision == "approve"
        assert result.decided_by == "rich"
        assert result.notes == "looks good"

    def test_dict_input_produces_new_instance_not_input(self) -> None:
        # The returned object must NOT be the input dict — it is a
        # freshly-validated typed instance.
        raw = _dict_payload()
        result = resume_value_as(ApprovalResponsePayload, raw)
        assert result is not raw  # type: ignore[comparison-overlap]

    def test_dict_input_with_invalid_field_raises_validation_error(self) -> None:
        # Pydantic should reject an unknown decision value.
        bad = dict(_dict_payload(), decision="not-a-real-decision")
        with pytest.raises(Exception) as exc_info:
            resume_value_as(ApprovalResponsePayload, bad)
        # Pydantic raises ValidationError; we just confirm the rejection.
        assert "decision" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# AC: Group D Scenario Outline — caller code is mode-agnostic.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("label", "raw_factory"),
    [
        ("typed_direct_invoke", _typed_payload),
        ("dict_server_mode", _dict_payload),
    ],
    ids=["typed_direct_invoke", "dict_server_mode"],
)
def test_group_d_scenario_outline_caller_code_is_mode_agnostic(
    label: str,
    raw_factory: object,
) -> None:
    """Group D ``Scenario Outline`` parametrised contract test.

    Same caller code observes a typed :class:`ApprovalResponsePayload`
    whether the input was a typed instance or a bare mapping of
    equivalent content. Closes risk **R2** (rehydration drift).
    """
    # Arrange — produce input via the parametrised factory.
    raw = raw_factory()  # type: ignore[operator]
    # Act — funnel through the helper, then exercise attribute access
    # exactly as a real ``interrupt()`` consumer would.
    typed = resume_value_as(ApprovalResponsePayload, raw)
    # Assert — attribute access works identically across both inputs.
    assert isinstance(typed, ApprovalResponsePayload)
    assert typed.decision == "approve"
    assert typed.decided_by == "rich"
    assert typed.request_id == _REQUEST_ID


# ---------------------------------------------------------------------------
# AC: clear ``TypeError`` for inputs that are neither ``typ`` nor ``dict``-like.
# ---------------------------------------------------------------------------


class TestRejectsUnsupportedInputs:
    """Inputs other than ``typ`` or ``dict`` MUST raise ``TypeError``."""

    @pytest.mark.parametrize(
        "bad_input",
        [
            42,
            "not-a-payload",
            None,
            [("request_id", "x"), ("decision", "approve")],  # list-of-tuples
            object(),
        ],
        ids=["int", "str", "none", "list_of_tuples", "object"],
    )
    def test_non_dict_non_typed_input_raises_type_error(
        self, bad_input: object
    ) -> None:
        with pytest.raises(TypeError) as exc_info:
            resume_value_as(ApprovalResponsePayload, bad_input)
        # Error message must reference the expected type and the actual
        # type so operators can diagnose without re-running with a debugger.
        msg = str(exc_info.value)
        assert "ApprovalResponsePayload" in msg
        assert "dict" in msg


# ---------------------------------------------------------------------------
# AC: module import purity — no ``nats_core`` / ``nats-py`` import.
# ---------------------------------------------------------------------------


class TestModuleImportPurity:
    """The adapter module must not depend on the NATS transport packages."""

    def test_langgraph_adapter_does_not_import_nats_core(self) -> None:
        # Parse the adapter module and inspect the **actual import**
        # nodes — docstring or comment mentions of ``nats_core`` are
        # explicitly allowed (e.g. for cross-references) so a literal
        # substring search would be too strict.
        repo_root = Path(__file__).resolve().parents[3]
        adapter = repo_root / "src" / "forge" / "adapters" / "langgraph" / "__init__.py"
        assert adapter.exists(), f"adapter module missing at {adapter}"
        tree = ast.parse(adapter.read_text(encoding="utf-8"))
        forbidden_roots = {"nats_core", "nats"}
        offenders: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".", 1)[0]
                    if root in forbidden_roots:
                        offenders.append(f"import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                root = node.module.split(".", 1)[0]
                if root in forbidden_roots:
                    offenders.append(f"from {node.module} import ...")
        assert not offenders, (
            "forge.adapters.langgraph must not import nats_core / nats-py "
            f"(DDR-002). Offending imports: {offenders}"
        )


# ---------------------------------------------------------------------------
# AC: CI grep guard — fail if any ``interrupt(`` is followed by
# ``.decision`` / ``.responder`` attribute access in the same function
# without an intervening ``resume_value_as`` call.
# ---------------------------------------------------------------------------


# Allow-list directive that suppresses the guard for a single line.
_REHYDRATION_GUARD_ALLOWLIST = "noqa: rehydration-guard"

#: Attribute names that are illegal to access on an unrehydrated
#: ``interrupt()`` resume value. ``decision`` and ``responder`` are the
#: two design-level field names from
#: ``API-nats-approval-protocol.md §4.1`` that DDR-002 specifically
#: calls out as silent-regression hazards under server mode.
_FORBIDDEN_ATTRS: frozenset[str] = frozenset({"decision", "responder"})


def _iter_forge_python_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[3]
    forge_root = repo_root / "src" / "forge"
    return [p for p in forge_root.rglob("*.py") if "__pycache__" not in p.parts]


def _callable_name(node: ast.expr) -> str | None:
    """Return the trailing dotted-name of a Call ``func`` expression.

    ``interrupt()``           -> ``"interrupt"``
    ``mod.interrupt()``       -> ``"interrupt"``
    ``self.interrupt()``      -> ``"interrupt"``
    Anything else (subscript, lambda, ...) returns ``None``.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _scan_function_for_violations(
    func: ast.FunctionDef | ast.AsyncFunctionDef,
    source_lines: list[str],
) -> list[tuple[int, str]]:
    """Return ``(line_no, snippet)`` tuples for unguarded interrupt consumers.

    A violation is a ``.decision`` / ``.responder`` :class:`ast.Attribute`
    access whose ``lineno`` is **strictly after** an ``interrupt()``
    Call's ``lineno`` in the same function and **strictly before** any
    ``resume_value_as()`` Call in that function. Lines carrying the
    ``# noqa: rehydration-guard`` allow-list directive are ignored.
    """
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
            # Attribute access strictly precedes any interrupt() — not
            # a rehydration consumer; safe.
            continue
        # Was the helper called between the first interrupt() and this
        # attribute access? If so, the value has been rehydrated.
        rehydrated = any(
            earliest_interrupt < hl <= attr_line for hl in helper_lines
        )
        if rehydrated:
            continue
        snippet = source_lines[attr_line - 1] if attr_line - 1 < len(source_lines) else ""
        if _REHYDRATION_GUARD_ALLOWLIST in snippet:
            continue
        violations.append((attr_line, snippet.rstrip()))
    return violations


def _scan_file_for_rehydration_violations(path: Path) -> list[tuple[int, str]]:
    text = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        # Skip files we cannot parse — those are not regression candidates
        # because they would also fail to import in CI.
        return []
    source_lines = text.splitlines()
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(_scan_function_for_violations(node, source_lines))
    return violations


def test_rehydration_grep_guard_no_unhelpered_interrupt_attribute_access() -> None:
    """No ``interrupt()`` consumer in ``forge/`` may bypass ``resume_value_as``.

    This is the CI grep guard half of the AC. It enforces DDR-002 by
    failing the test suite the moment any new code introduces an
    ``interrupt(...) -> .decision``/``.responder`` access path that
    skips :func:`resume_value_as`.

    Suppress for an intentional exception with the inline comment
    ``# noqa: rehydration-guard`` on the offending line.
    """
    offenders: list[str] = []
    for path in _iter_forge_python_files():
        for line_no, snippet in _scan_file_for_rehydration_violations(path):
            offenders.append(f"{path}:{line_no}: {snippet}")
    assert not offenders, (
        "DDR-002 regression: interrupt() consumer reads .decision/.responder "
        "without going through resume_value_as. Offenders:\n"
        + "\n".join(offenders)
    )


def test_rehydration_grep_guard_detects_synthetic_violation(
    tmp_path: Path,
) -> None:
    """Confidence test: scanner flags a synthetic regression.

    Build a tiny module that fakes the regression pattern and confirm
    :func:`_scan_file_for_rehydration_violations` reports it. This
    proves the scanner is not silently passing every file.
    """
    bad = tmp_path / "bad.py"
    bad.write_text(
        "async def consume():\n"
        "    raw = await interrupt({})\n"
        "    return raw.decision\n",
        encoding="utf-8",
    )
    violations = _scan_file_for_rehydration_violations(bad)
    assert violations, "scanner failed to detect synthetic regression"
    line_no, snippet = violations[0]
    assert line_no == 3
    assert ".decision" in snippet


def test_rehydration_grep_guard_respects_allowlist_directive(
    tmp_path: Path,
) -> None:
    """A ``# noqa: rehydration-guard`` comment suppresses one line."""
    allowed = tmp_path / "allowed.py"
    allowed.write_text(
        "async def consume():\n"
        "    raw = await interrupt({})\n"
        "    return raw.decision  # noqa: rehydration-guard\n",
        encoding="utf-8",
    )
    assert _scan_file_for_rehydration_violations(allowed) == []


def test_rehydration_grep_guard_accepts_helpered_access(
    tmp_path: Path,
) -> None:
    """An intervening ``resume_value_as`` call clears the consumer."""
    ok = tmp_path / "ok.py"
    ok.write_text(
        "async def consume():\n"
        "    raw = await interrupt({})\n"
        "    typed = resume_value_as(object, raw)\n"
        "    return typed.decision\n",
        encoding="utf-8",
    )
    assert _scan_file_for_rehydration_violations(ok) == []
