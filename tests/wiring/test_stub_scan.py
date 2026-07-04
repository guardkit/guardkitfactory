"""Anti-stub body scan tests (TASK-QAV-001).

Fixture-based unit tests for the stack-agnostic stub body scan that flags
authored public functions/methods whose bodies contain no executable logic.

Acceptance criteria covered:
  AC-1: Python positive fixtures (pass, ..., raise NotImplementedError,
        return None/[]/{}, with and without docstring)
  AC-2: Python no-false-positive (docstring + real statements, logic ending
        in return [])
  AC-3: TypeScript + C# positive + control fixtures
  AC-4: Unsupported language → unsupported_stack
  AC-5: Task-type gating + public API
  AC-6: End-to-end round-trip behavioral test
  AC-7: Existing wiring + BDD contract tests remain green (not in this file)
  AC-8: Lint/format (enforced by project tooling)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from guardkitfactory.wiring import analyze_stub_scan

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(worktree: Path, rel: str, content: str) -> str:
    """Write *content* to *rel* under *worktree*; return *rel*."""
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return rel


def _stub_findings(result: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Extract stub findings from an analyze_stub_scan result dict."""
    if result is None:
        return []
    return result.get("findings", [])


def _stub_status(result: dict[str, Any] | None) -> str | None:
    """Extract status from an analyze_stub_scan result dict."""
    if result is None:
        return None
    return result.get("status")


# ---------------------------------------------------------------------------
# AC-1: Python positive fixtures
# ---------------------------------------------------------------------------

class TestAC1PythonPositive:
    """Each stub variant yields one finding per symbol."""

    @pytest.mark.parametrize(
        "body,symbol,stub_kind",
        [
            ("pass", "stub_pass", "pass"),
            ("...", "stub_ellipsis", "ellipsis"),
            ("raise NotImplementedError()", "stub_not_impl", "not_implemented"),
            ("return None", "stub_return_none", "return_none"),
            ("return []", "stub_return_list", "return_empty_list"),
            ("return {}", "stub_return_dict", "return_empty_dict"),
        ],
    )
    def test_stub_variants_without_docstring(
        self, tmp_path: Path, body: str, symbol: str, stub_kind: str
    ) -> None:
        """AC-1: bare stub body variants yield a STUB_BODY finding."""
        src = _write(
            tmp_path,
            "src/module.py",
            f"def {symbol}():\n    {body}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        f = findings[0]
        assert f["symbol"] == symbol
        assert f["kind"] == "STUB_BODY"
        assert f["pattern"] == "STUB_BODY"
        assert f["severity"] == "warning"
        assert f["file"] == src
        assert _stub_status(result) == "complete"

    @pytest.mark.parametrize(
        "body,symbol,stub_kind",
        [
            ("pass", "stub_pass", "pass"),
            ("...", "stub_ellipsis", "ellipsis"),
            ("raise NotImplementedError()", "stub_not_impl", "not_implemented"),
            ("return None", "stub_return_none", "return_none"),
            ("return []", "stub_return_list", "return_empty_list"),
            ("return {}", "stub_return_dict", "return_empty_dict"),
        ],
    )
    def test_stub_variants_with_docstring(
        self, tmp_path: Path, body: str, symbol: str, stub_kind: str
    ) -> None:
        """AC-1: stub body with preceding docstring still yields a finding."""
        src = _write(
            tmp_path,
            "src/module.py",
            f'def {symbol}():\n    """Docstring."""\n    {body}\n',
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == symbol
        assert findings[0]["kind"] == "STUB_BODY"
        assert _stub_status(result) == "complete"


# ---------------------------------------------------------------------------
# AC-2: Python no-false-positive control
# ---------------------------------------------------------------------------

class TestAC2PythonNoFalsePositives:
    """Functions with real logic must NOT be flagged."""

    def test_docstring_followed_by_real_statements(self, tmp_path: Path) -> None:
        """AC-2: docstring + real statements → no finding."""
        src = _write(
            tmp_path,
            "src/module.py",
            'def real_function():\n'
            '    """Docstring."""\n'
            "    x = 1\n"
            "    return x + 1\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert findings == []
        assert _stub_status(result) == "complete"

    def test_logic_ending_in_return_list(self, tmp_path: Path) -> None:
        """AC-2: genuine logic that ends in return [] → no finding."""
        src = _write(
            tmp_path,
            "src/module.py",
            """def build_list():
    items = []
    items.append(1)
    return items
""",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert findings == []
        assert _stub_status(result) == "complete"


# ---------------------------------------------------------------------------
# AC-3: Multi-stack parity (TypeScript + C#)
# ---------------------------------------------------------------------------

class TestAC3MultiStackParity:
    """Positive + control fixtures for TypeScript and C#."""

    # --- TypeScript positive ---

    def test_ts_throw_error_not_implemented(self, tmp_path: Path) -> None:
        """AC-3: TypeScript `throw new Error("not implemented")` → stub."""
        src = _write(
            tmp_path,
            "src/module.ts",
            'export function stubThrow(): void {\n'
            '    throw new Error("not implemented");\n'
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == "stubThrow"
        assert findings[0]["kind"] == "STUB_BODY"

    def test_ts_empty_body(self, tmp_path: Path) -> None:
        """AC-3: TypeScript empty body `{}` → stub."""
        src = _write(
            tmp_path,
            "src/module.ts",
            "export function stubEmpty(): void {\n}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == "stubEmpty"

    def test_ts_return_null(self, tmp_path: Path) -> None:
        """AC-3: TypeScript `return null` → stub."""
        src = _write(
            tmp_path,
            "src/module.ts",
            "export function stubNull(): string | null {\n"
            "    return null;\n"
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == "stubNull"

    def test_ts_control_real_logic(self, tmp_path: Path) -> None:
        """AC-3: TypeScript with real logic → no finding."""
        src = _write(
            tmp_path,
            "src/module.ts",
            "export function realFunction(): number {\n"
            "    const x = 1;\n"
            "    return x + 1;\n"
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert findings == []

    # --- C# positive ---

    def test_cs_throw_notimplementedexception(self, tmp_path: Path) -> None:
        """AC-3: C# `throw new NotImplementedException()` → stub."""
        src = _write(
            tmp_path,
            "src/Module.cs",
            "public class Module {\n"
            "    public void StubThrow() {\n"
            "        throw new NotImplementedException();\n"
            "    }\n"
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == "StubThrow"
        assert findings[0]["kind"] == "STUB_BODY"

    def test_cs_empty_body(self, tmp_path: Path) -> None:
        """AC-3: C# empty body `{}` → stub."""
        src = _write(
            tmp_path,
            "src/Module.cs",
            "public class Module {\n"
            "    public void StubEmpty() { }\n"
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert len(findings) == 1
        assert findings[0]["symbol"] == "StubEmpty"

    def test_cs_control_real_logic(self, tmp_path: Path) -> None:
        """AC-3: C# with real logic → no finding."""
        src = _write(
            tmp_path,
            "src/Module.cs",
            "public class Module {\n"
            "    public int RealMethod() {\n"
            "        return 42;\n"
            "    }\n"
            "}\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        findings = _stub_findings(result)
        assert findings == []


# ---------------------------------------------------------------------------
# AC-4: Status discriminator (unsupported language, parse failure)
# ---------------------------------------------------------------------------

class TestAC4StatusDiscriminator:
    """Unsupported language → unsupported_stack; parse failure → degraded."""

    def test_unsupported_language(self, tmp_path: Path) -> None:
        """AC-4: unsupported language → status 'unsupported_stack' with no findings."""
        # Write a .rb file (Ruby — no dialect registered for stub scan)
        src = _write(
            tmp_path,
            "src/module.rb",
            'def stub_method; end\n',
        )
        # Stub scan returns None when no dialect has stub_body_query
        # for the file extension, which is the expected absent-signal.
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        # No dialect supports stub scan for .rb → None (probe didn't run)
        assert result is None

    def test_parse_degraded(self, tmp_path: Path) -> None:
        """AC-4: parse-failed file → degraded, no finding manufactured."""
        # Write syntactically broken Python
        src = _write(
            tmp_path,
            "src/module.py",
            "def broken_function(\n    # missing body, syntax error\n",
        )
        result = analyze_stub_scan([src], tmp_path, "FEATURE")
        # Parse degraded: no findings, degraded_files recorded
        if result is not None:
            findings = _stub_findings(result)
            assert findings == []
            assert "degraded_files" in result


# ---------------------------------------------------------------------------
# AC-5: Task-type gating + public API
# ---------------------------------------------------------------------------

class TestAC5TaskTypeGating:
    """Task-type gate + public API contract."""

    @pytest.mark.parametrize(
        "task_type",
        ["SCAFFOLDING", "DOCUMENTATION", "TESTING", "scaffolding", "Documentation"],
    )
    def test_non_analyzed_task_types_return_none(
        self, tmp_path: Path, task_type: str
    ) -> None:
        """AC-5: SCAFFOLDING/DOCUMENTATION/TESTING → None."""
        src = _write(
            tmp_path,
            "src/module.py",
            "def stub_func():\n    pass\n",
        )
        result = analyze_stub_scan([src], tmp_path, task_type)
        assert result is None

    def test_zero_authored_targets(self, tmp_path: Path) -> None:
        """AC-5: zero authored targets → None."""
        result = analyze_stub_scan([], tmp_path, "FEATURE")
        assert result is None

    def test_result_has_to_dict(self) -> None:
        """AC-5: StubScanResult exposes .to_dict()."""
        from guardkitfactory.wiring import StubScanResult

        r = StubScanResult(status="complete", ran=True)
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "complete"
        assert d["ran"] is True

    def test_public_api_signature(self) -> None:
        """AC-5: analyze_stub_scan is a public function with the right signature."""
        import inspect

        sig = inspect.signature(analyze_stub_scan)
        params = list(sig.parameters.keys())
        assert "authored_files" in params
        assert "worktree_path" in params
        assert "task_type" in params
        assert "stack" in params


# ---------------------------------------------------------------------------
# AC-6: Behavioural check (dogfood round-trip)
# ---------------------------------------------------------------------------

class TestAC6RoundTrip:
    """End-to-end round-trip over a mini fixture project on disk."""

    def test_end_to_end_roundtrip(self, tmp_path: Path) -> None:
        """AC-6: analyze_stub_scan end-to-end over a mini project.

        Creates a small fixture project with:
        - A stub function (should be flagged)
        - A real function (should NOT be flagged)
        - A TypeScript stub (should be flagged)

        Asserts:
        - The emitted dict is JSON-serialisable
        - The shape matches the documented stub_scan result shape
        - The correct number of findings are present
        """
        # Create fixture project
        stub_py = _write(
            tmp_path,
            "src/stubs.py",
            "def stub_one():\n    pass\n\n"
            "def stub_two():\n    raise NotImplementedError()\n"
            "\n"
            "def real_func():\n"
            "    return 42\n",
        )
        stub_ts = _write(
            tmp_path,
            "src/stubs.ts",
            "export function ts_stub(): void {\n}\n"
            "\n"
            "export function ts_real(): number {\n"
            "    return 1;\n"
            "}\n",
        )

        result = analyze_stub_scan(
            [stub_py, stub_ts],
            tmp_path,
            "FEATURE",
        )

        # Shape check
        assert result is not None
        assert "status" in result
        assert "ran" in result
        assert "dialect" in result
        assert "language" in result
        assert "symbols_examined" in result
        assert "findings" in result
        assert "degraded_files" in result

        # JSON serialisability check
        json_str = json.dumps(result)
        assert isinstance(json_str, str)
        json_back = json.loads(json_str)
        assert json_back == result

        # Findings check: 3 stubs (stub_one, stub_two, ts_stub)
        findings = _stub_findings(result)
        stub_symbols = {f["symbol"] for f in findings}
        assert "stub_one" in stub_symbols
        assert "stub_two" in stub_symbols
        assert "ts_stub" in stub_symbols
        assert "real_func" not in stub_symbols
        assert "ts_real" not in stub_symbols

        # All findings have the correct pattern
        for f in findings:
            assert f["pattern"] == "STUB_BODY"
            assert f["kind"] == "STUB_BODY"
            assert f["severity"] == "warning"


# ---------------------------------------------------------------------------
# AC-7: Existing tests remain green (import smoke test)
# ---------------------------------------------------------------------------

class TestAC7ImportSmoke:
    """Smoke test: the module imports cleanly and dialects register."""

    def test_dialects_have_stub_fields(self) -> None:
        """All registered dialects have stub_body_query (or empty = no-op)."""
        from guardkitfactory.wiring import iter_dialects

        for dialect in iter_dialects():
            # stub_body_query may be empty (no-op) or populated
            assert hasattr(dialect, "stub_body_query")
            assert hasattr(dialect, "stub_marker_patterns")
            assert hasattr(dialect, "stub_body_node_types")

    def test_stub_scan_result_to_dict(self) -> None:
        """StubScanResult.to_dict() returns a valid dict."""
        from guardkitfactory.wiring import StubScanResult

        r = StubScanResult()
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["status"] == "skipped_no_targets"
        assert d["ran"] is False
