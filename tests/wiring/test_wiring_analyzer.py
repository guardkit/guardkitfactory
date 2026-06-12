"""WiringAnalyzer tests: stack-agnostic wiring-analysis engine (TASK-QAWE-001).

Maps tests to acceptance criteria:
- AC-019: tree-sitter API path pinned + smoke_test() canonical-snippet match
- AC-020: dependency declaration + packaging + namespace hygiene
- AC-001/002: UNWIRED positive + wired control (Python)
- AC-003: UNWIRED positive + control (C#)
- AC-004: UNWIRED positive + control (TS/JS)
- AC-005/006: MOCKED_SEAM positive + external allowlist control (Python)
- AC-007: MOCKED_SEAM positive + allowlist control (C#)
- AC-008: task-type gate + zero-authored-targets → None
- AC-009: unsupported stack → absent-signal (never "complete")
- AC-010: parse-degraded biases WIRED
- AC-021: polyglot — one call runs ALL matching dialects
- AC-015 spirit: absent (None) vs empty-findings-positive are distinct
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardkitfactory.wiring import analyze_wiring


@pytest.fixture()
def tmp_worktree(tmp_path: Path) -> Path:
    """A temporary worktree directory."""
    return tmp_path


def _write(worktree: Path, rel: str, content: str) -> str:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return rel


# ---------------------------------------------------------------------------
# AC-019: tree-sitter API path + smoke_test()
# ---------------------------------------------------------------------------


class TestAC019:
    """Parse via get_language() + standalone Parser (bytes) +
    QueryCursor(query).captures(root); smoke_test compiles AND matches."""

    def test_smoke_test_all_dialects(self) -> None:
        """All four built-in dialects pass smoke_test()."""
        from guardkitfactory.wiring.dialect import iter_dialects

        for dialect in iter_dialects():
            assert dialect.smoke_test() is True, (
                f"smoke_test failed for dialect '{dialect.language}'"
            )

    def test_smoke_test_catches_capture_nothing_query(self) -> None:
        """A query that compiles but captures nothing FAILS smoke_test —
        the AC-019 'malformed query must fail in Wave 0' guarantee."""
        import dataclasses

        from guardkitfactory.wiring.dialect import get_dialect

        py = get_dialect("python")
        assert py is not None
        broken = dataclasses.replace(
            py,
            # Compiles fine; can never capture @name from the snippet.
            public_symbols_query="(import_statement) @name",
        )
        assert broken.smoke_test() is False

    def test_parser_uses_standalone_api(self) -> None:
        """Standalone Parser + QueryCursor path works end-to-end."""
        from tree_sitter import Parser, Query, QueryCursor
        from tree_sitter_language_pack import get_language

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"def hello(): pass")
        assert tree.root_node.type == "module"

        query = Query(lang, "(function_definition name: (identifier) @name)")
        captures = QueryCursor(query).captures(tree.root_node)
        assert "name" in captures and len(captures["name"]) == 1

    def test_wiring_parser_module_does_not_use_pack_get_parser(self) -> None:
        """parser.py must not call the pack's get_parser() (AC-019)."""
        import guardkitfactory.wiring.parser as parser_mod

        src = Path(parser_mod.__file__).read_text()
        assert "tree_sitter_language_pack import get_parser" not in src
        assert "from tree_sitter_language_pack import get_language" in src


# ---------------------------------------------------------------------------
# AC-020: dependency declaration + packaging + namespace hygiene
# ---------------------------------------------------------------------------


def _pyproject() -> dict:
    import tomllib

    path = Path(__file__).parents[2] / "pyproject.toml"
    assert path.is_file(), f"pyproject.toml not found at {path}"
    with open(path, "rb") as f:
        return tomllib.load(f)


class TestAC020:
    """Deps in core [project] dependencies; packages include wiring +
    wiring.dialects; new module names shadow no PyPI top-level package."""

    def test_tree_sitter_in_core_dependencies(self) -> None:
        deps = _pyproject()["project"]["dependencies"]
        assert any(d.startswith("tree-sitter>=") for d in deps), deps
        assert any(d.startswith("tree-sitter-language-pack>=") for d in deps), deps

    def test_wiring_packages_in_setuptools_config(self) -> None:
        packages = _pyproject()["tool"]["setuptools"]["packages"]
        assert "guardkitfactory.wiring" in packages
        assert "guardkitfactory.wiring.dialects" in packages

    def test_wiring_module_names_shadow_no_pypi_top_level(self) -> None:
        """Namespace hygiene: the SHIPPED modules are importable ONLY under
        the guardkitfactory.wiring namespace — `import wiring` / `import
        dialect` etc. must never resolve into src/guardkitfactory (no
        top-level shadowing per .claude/rules/namespace-hygiene.md)."""
        import importlib.util

        for name in ("wiring", "dialect", "parser", "analyzer"):
            spec = importlib.util.find_spec(name)
            if spec is not None and spec.origin is not None:
                origin = Path(spec.origin)
                assert "src" not in origin.parts or (
                    "guardkitfactory" not in origin.parts
                ), (
                    f"module '{name}' leaks as a top-level import "
                    f"from {spec.origin}"
                )

    def test_wiring_public_api_importable(self) -> None:
        from guardkitfactory.wiring import (
            Finding,  # noqa: F401
            MockSeamResult,  # noqa: F401
            WiringDialect,  # noqa: F401
            WiringResult,  # noqa: F401
            analyze_wiring,
            get_dialect,
        )

        assert callable(analyze_wiring)
        assert callable(get_dialect)


# ---------------------------------------------------------------------------
# AC-001 / AC-002: UNWIRED positive + wired control — Python
# ---------------------------------------------------------------------------


class TestUnwiredPython:
    def test_ac001_unwired_positive(self, tmp_worktree: Path) -> None:
        """Exactly one finding for the un-wired symbol, with the pinned
        finding contract: kind, registration_found:false, searched_refs:0,
        status:'complete'."""
        _write(tmp_worktree, "app.py", "def my_command():\n    pass\n")

        result = analyze_wiring(["app.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        findings = result["findings"]
        assert len(findings) == 1
        f = findings[0]
        assert f["symbol"] == "my_command"
        assert f["kind"] == "function"
        assert f["pattern"] == "UNWIRED_PATH"
        assert f["registration_found"] is False
        assert f["searched_refs"] == 0
        assert f["severity"] == "warning"
        assert f["dialect"] == "python" and f["language"] == "python"

    def test_ac002_wired_control_via_reference(self, tmp_worktree: Path) -> None:
        """Symbol referenced by another non-test module → findings:[],
        status:'complete' (no false positive)."""
        _write(tmp_worktree, "producer.py", "def my_service():\n    pass\n")
        _write(
            tmp_worktree,
            "consumer.py",
            "from producer import my_service\nmy_service()\n",
        )

        result = analyze_wiring(["producer.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["findings"] == []

    def test_ac002_wired_control_via_registration(self, tmp_worktree: Path) -> None:
        """cli.add_command(X) in a SEPARATE file wires X (registration path,
        mirroring guardkit/cli/main.py)."""
        _write(tmp_worktree, "commands.py", "def my_command():\n    pass\n")
        _write(
            tmp_worktree,
            "main.py",
            "import commands\ncli.add_command(commands.my_command)\n",
        )

        result = analyze_wiring(["commands.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["findings"] == []

    def test_referenced_only_by_own_test_is_unwired(self, tmp_worktree: Path) -> None:
        """THE core detection: a symbol referenced ONLY from its own unit
        test is dead code — must produce an UNWIRED finding."""
        _write(tmp_worktree, "orphan.py", "def orphan_service():\n    pass\n")
        _write(
            tmp_worktree,
            "tests/test_orphan.py",
            "from orphan import orphan_service\n"
            "def test_it():\n    assert orphan_service() is None\n",
        )

        result = analyze_wiring(["orphan.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert {f["symbol"] for f in result["findings"]} == {"orphan_service"}

    def test_private_symbol_not_flagged(self, tmp_worktree: Path) -> None:
        """Leading-underscore privates are not UNWIRED candidates."""
        _write(tmp_worktree, "helpers.py", "def _private_helper():\n    pass\n")

        result = analyze_wiring(["helpers.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["findings"] == []

    def test_dunder_all_counts_as_wired(self, tmp_worktree: Path) -> None:
        """A symbol listed in __all__ counts as wired."""
        _write(
            tmp_worktree,
            "api.py",
            '__all__ = ["exported_func"]\n\ndef exported_func():\n    pass\n',
        )

        result = analyze_wiring(["api.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["findings"] == []

    def test_manifest_entry_counts_as_wired(self, tmp_worktree: Path) -> None:
        """A symbol named in pyproject.toml (e.g. [project.scripts]) is wired."""
        _write(tmp_worktree, "cli.py", "def main_entry():\n    pass\n")
        _write(
            tmp_worktree,
            "pyproject.toml",
            '[project.scripts]\nmytool = "cli:main_entry"\n',
        )

        result = analyze_wiring(["cli.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["findings"] == []

    def test_decorated_symbol_is_visible(self, tmp_worktree: Path) -> None:
        """Decorated module-level defs are extracted (decorated_definition)."""
        _write(
            tmp_worktree,
            "cmds.py",
            "@some_decorator\ndef decorated_orphan():\n    pass\n",
        )

        result = analyze_wiring(["cmds.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert {f["symbol"] for f in result["findings"]} == {"decorated_orphan"}


# ---------------------------------------------------------------------------
# AC-003: UNWIRED positive + control — C#
# ---------------------------------------------------------------------------


class TestUnwiredCSharp:
    def test_ac003_unwired_positive(self, tmp_worktree: Path) -> None:
        """An un-registered public C# class yields one finding."""
        _write(
            tmp_worktree,
            "OrphanService.cs",
            "public class OrphanService { }\n",
        )

        result = analyze_wiring(["OrphanService.cs"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert {f["symbol"] for f in result["findings"]} == {"OrphanService"}
        assert result["findings"][0]["language"] == "c_sharp"

    def test_ac003_wired_control_addscoped(self, tmp_worktree: Path) -> None:
        """services.AddScoped<X>() in another file wires X."""
        _write(tmp_worktree, "MyService.cs", "public class MyService { }\n")
        _write(
            tmp_worktree,
            "Startup.cs",
            "public class Startup {\n"
            "    public void Configure(IServiceCollection services) {\n"
            "        services.AddScoped<MyService>();\n"
            "    }\n"
            "}\n",
        )

        result = analyze_wiring(["MyService.cs"], tmp_worktree, "FEATURE")

        assert result is not None
        assert "MyService" not in {f["symbol"] for f in result["findings"]}

    def test_non_public_csharp_symbol_not_flagged(self, tmp_worktree: Path) -> None:
        """private/protected members are not UNWIRED candidates."""
        _write(
            tmp_worktree,
            "Internals.cs",
            "public class Wrapper {\n"
            "    private void HiddenHelper() { }\n"
            "}\n",
        )
        _write(tmp_worktree, "User.cs", "public class User { Wrapper w; }\n")

        result = analyze_wiring(["Internals.cs"], tmp_worktree, "FEATURE")

        assert result is not None
        assert "HiddenHelper" not in {f["symbol"] for f in result["findings"]}


# ---------------------------------------------------------------------------
# AC-004: UNWIRED positive + control — TS/JS
# ---------------------------------------------------------------------------


class TestUnwiredTsJs:
    def test_ac004_unwired_positive_ts(self, tmp_worktree: Path) -> None:
        """An exported-but-unreferenced TS class yields one finding."""
        _write(tmp_worktree, "orphan.ts", "export class TsOrphan {}\n")

        result = analyze_wiring(["orphan.ts"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert {f["symbol"] for f in result["findings"]} == {"TsOrphan"}

    def test_ac004_wired_control_app_use(self, tmp_worktree: Path) -> None:
        """app.use(X) from another module wires X."""
        _write(tmp_worktree, "handler.ts", "export class MyHandler {}\n")
        _write(
            tmp_worktree,
            "server.ts",
            'import { MyHandler } from "./handler";\napp.use(MyHandler);\n',
        )

        result = analyze_wiring(["handler.ts"], tmp_worktree, "FEATURE")

        assert result is not None
        assert "MyHandler" not in {f["symbol"] for f in result["findings"]}

    def test_unexported_js_symbol_not_flagged(self, tmp_worktree: Path) -> None:
        """A non-exported top-level JS function is module-private."""
        _write(
            tmp_worktree,
            "util.js",
            "function internalOnly() {}\nexport function used() { internalOnly(); }\n",
        )
        _write(tmp_worktree, "main.js", 'import { used } from "./util";\nused();\n')

        result = analyze_wiring(["util.js"], tmp_worktree, "FEATURE")

        assert result is not None
        assert "internalOnly" not in {f["symbol"] for f in result["findings"]}


# ---------------------------------------------------------------------------
# AC-005 / AC-006: MOCKED_SEAM — Python
# ---------------------------------------------------------------------------


class TestMockedSeamPython:
    def test_ac005_mocked_authored_seam(self, tmp_worktree: Path) -> None:
        """An acceptance file patch()-ing an authored seam yields one
        mocked_seam finding with authored_this_turn:true, severity warning."""
        _write(tmp_worktree, "authored.py", "def my_authored_seam():\n    pass\n")
        _write(tmp_worktree, "main.py", "from authored import my_authored_seam\n")
        _write(
            tmp_worktree,
            "features/steps.py",
            "from unittest.mock import patch\n"
            "@patch('authored.my_authored_seam')\n"
            "def step_impl(mock_seam):\n    pass\n",
        )

        result = analyze_wiring(["authored.py"], tmp_worktree, "FEATURE")

        assert result is not None
        seam = result["mocked_seam"]
        assert seam["ran"] is True and seam["status"] == "ran"
        warnings = [f for f in seam["findings"] if f["severity"] == "warning"]
        assert len(warnings) == 1
        assert warnings[0]["authored_this_turn"] is True
        assert "my_authored_seam" in warnings[0]["symbol"]
        assert warnings[0]["pattern"] == "MOCKED_SEAM"

    def test_ac006_external_mock_allowlisted(self, tmp_worktree: Path) -> None:
        """Mocking httpx (allow-listed) → no warning finding; the target is
        RECORDED under external_mocks_ignored."""
        _write(tmp_worktree, "app.py", "def my_service():\n    pass\n")
        _write(tmp_worktree, "main.py", "from app import my_service\n")
        _write(
            tmp_worktree,
            "features/steps.py",
            "from unittest.mock import patch\n"
            "@patch('httpx.Client')\n"
            "def step_impl(mock_client):\n    pass\n",
        )

        result = analyze_wiring(["app.py"], tmp_worktree, "FEATURE")

        assert result is not None
        seam = result["mocked_seam"]
        assert [f for f in seam["findings"] if f["severity"] == "warning"] == []
        ignored = seam["external_mocks_ignored"]
        assert any("httpx" in f["symbol"] for f in ignored)

    def test_third_party_mock_surfaced_as_info(self, tmp_worktree: Path) -> None:
        """A mock that is neither authored nor allow-listed surfaces as
        severity:'info' — not dropped."""
        _write(tmp_worktree, "app.py", "def my_service():\n    pass\n")
        _write(tmp_worktree, "main.py", "from app import my_service\n")
        _write(
            tmp_worktree,
            "features/steps.py",
            "from unittest.mock import patch\n"
            "@patch('thirdparty.engine.Thing')\n"
            "def step_impl(m):\n    pass\n",
        )

        result = analyze_wiring(["app.py"], tmp_worktree, "FEATURE")

        assert result is not None
        infos = [
            f for f in result["mocked_seam"]["findings"] if f["severity"] == "info"
        ]
        assert any("thirdparty" in f["symbol"] for f in infos)

    def test_plain_calls_in_acceptance_not_mock_targets(
        self, tmp_worktree: Path
    ) -> None:
        """Ordinary calls in acceptance files must NOT register as mock
        targets (the mock query is anchored to mock primitives)."""
        _write(tmp_worktree, "app.py", "def my_service():\n    pass\n")
        _write(
            tmp_worktree,
            "features/steps.py",
            "from app import my_service\n"
            "def step_impl():\n    result = my_service()\n    assert result\n",
        )

        result = analyze_wiring(["app.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["mocked_seam"]["findings"] == []


# ---------------------------------------------------------------------------
# AC-007: MOCKED_SEAM — C#
# ---------------------------------------------------------------------------


class TestMockedSeamCSharp:
    def test_ac007_mock_of_authored_interface(self, tmp_worktree: Path) -> None:
        """new Mock<IAuthoredSeam>() against an authored type → warning;
        the @target is the generic TYPE argument."""
        _write(
            tmp_worktree,
            "IAuthoredSeam.cs",
            "public interface IAuthoredSeam { }\n",
        )
        _write(
            tmp_worktree,
            "Program.cs",
            "public class Program { IAuthoredSeam s; }\n",
        )
        _write(
            tmp_worktree,
            "features/Steps.cs",
            "using Moq;\n"
            "public class Steps {\n"
            "    public void Setup() {\n"
            "        var mock = new Mock<IAuthoredSeam>();\n"
            "    }\n"
            "}\n",
        )

        result = analyze_wiring(["IAuthoredSeam.cs"], tmp_worktree, "FEATURE")

        assert result is not None
        warnings = [
            f
            for f in result["mocked_seam"]["findings"]
            if f["severity"] == "warning"
        ]
        assert len(warnings) == 1
        assert warnings[0]["symbol"] == "IAuthoredSeam"
        assert warnings[0]["authored_this_turn"] is True

    def test_ac007_allowlisted_mock_not_flagged(self, tmp_worktree: Path) -> None:
        """Mock<HttpClient> (allow-listed) → recorded, never a warning."""
        _write(tmp_worktree, "Svc.cs", "public class Svc { }\n")
        _write(tmp_worktree, "Program.cs", "public class Program { Svc s; }\n")
        _write(
            tmp_worktree,
            "features/Steps.cs",
            "using Moq;\n"
            "public class Steps {\n"
            "    public void Setup() {\n"
            "        var mock = new Mock<HttpClient>();\n"
            "    }\n"
            "}\n",
        )

        result = analyze_wiring(["Svc.cs"], tmp_worktree, "FEATURE")

        assert result is not None
        seam = result["mocked_seam"]
        assert [f for f in seam["findings"] if f["severity"] == "warning"] == []
        assert any(
            "HttpClient" in f["symbol"] for f in seam["external_mocks_ignored"]
        )


# ---------------------------------------------------------------------------
# AC-008: task-type gate + zero-authored-targets → None
# ---------------------------------------------------------------------------


class TestAC008:
    def test_non_feature_task_returns_none(self, tmp_worktree: Path) -> None:
        _write(tmp_worktree, "app.py", "def f():\n    pass\n")
        for task_type in ("DOCUMENTATION", "SCAFFOLDING", "TESTING", ""):
            assert analyze_wiring(["app.py"], tmp_worktree, task_type) is None

    def test_task_type_gate_is_case_insensitive(self, tmp_worktree: Path) -> None:
        """guardkit frontmatter uses lowercase task_type values."""
        _write(tmp_worktree, "app.py", "def lonely():\n    pass\n")
        result = analyze_wiring(["app.py"], tmp_worktree, "feature")
        assert result is not None and result["status"] == "complete"

    def test_zero_authored_source_targets_returns_none(
        self, tmp_worktree: Path
    ) -> None:
        """Docs-only turns: probe legitimately did not run → None."""
        _write(tmp_worktree, "README.md", "# docs only\n")
        _write(tmp_worktree, "app.py", "def preexisting():\n    pass\n")

        assert analyze_wiring(["README.md"], tmp_worktree, "FEATURE") is None

    def test_test_only_turn_returns_none(self, tmp_worktree: Path) -> None:
        """Authoring only test files → zero non-test targets → None."""
        _write(tmp_worktree, "tests/test_app.py", "def test_it():\n    pass\n")

        assert (
            analyze_wiring(["tests/test_app.py"], tmp_worktree, "FEATURE") is None
        )

    def test_preexisting_code_never_flagged(self, tmp_worktree: Path) -> None:
        """Targets are the AUTHORED set: pre-existing dead code in the
        worktree must not be attributed to this turn."""
        _write(tmp_worktree, "legacy.py", "def legacy_orphan():\n    pass\n")
        _write(tmp_worktree, "newwork.py", "def new_orphan():\n    pass\n")

        result = analyze_wiring(["newwork.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert {f["symbol"] for f in result["findings"]} == {"new_orphan"}


# ---------------------------------------------------------------------------
# AC-009: unsupported stack → absent-signal
# ---------------------------------------------------------------------------


class TestAC009:
    def test_unsupported_stack_via_stack_profile(self, tmp_worktree: Path) -> None:
        _write(tmp_worktree, "app.rb", "def my_method\nend\n")

        class StackProfile:
            language = "ruby"

        result = analyze_wiring(
            ["app.rb"], tmp_worktree, "FEATURE", stack=StackProfile()
        )

        assert result is not None
        assert result["status"] == "unsupported_stack"
        assert result["findings"] == []
        assert result["status"] != "complete"
        assert result["mocked_seam"]["status"] == "unsupported_stack"

    def test_unsupported_stack_inferred_from_extension(
        self, tmp_worktree: Path
    ) -> None:
        """No stack profile, known-but-undialected extension (.go) →
        unsupported_stack, NOT a silent None."""
        _write(tmp_worktree, "main.go", "package main\nfunc main() {}\n")

        result = analyze_wiring(["main.go"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "unsupported_stack"
        assert result["language"] == "go"


# ---------------------------------------------------------------------------
# AC-010: parse-degraded biases WIRED
# ---------------------------------------------------------------------------


class TestAC010:
    def test_parse_degraded_status_and_no_false_unwired(
        self, tmp_worktree: Path
    ) -> None:
        """A target with a CST parse error is skipped (never flagged) and
        the run reports parse_degraded with the file recorded."""
        _write(
            tmp_worktree,
            "broken.py",
            "def my_function(\n    # invalid syntax - unclosed paren\n",
        )

        result = analyze_wiring(["broken.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "parse_degraded"
        assert result["degraded_files"] == ["broken.py"]
        assert result["findings"] == []

    def test_symbol_free_valid_file_is_not_degraded(
        self, tmp_worktree: Path
    ) -> None:
        """A valid file with zero public symbols is NOT parse-degraded —
        degradation means CST error, not 'nothing found'."""
        _write(tmp_worktree, "constants.py", "X = 1\nY = 2\n")

        result = analyze_wiring(["constants.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["degraded_files"] == []

    def test_valid_and_broken_mix(self, tmp_worktree: Path) -> None:
        """Valid targets still classify while broken ones degrade."""
        _write(tmp_worktree, "good.py", "def good_orphan():\n    pass\n")
        _write(tmp_worktree, "bad.py", "def broken(\n")

        result = analyze_wiring(["good.py", "bad.py"], tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "parse_degraded"
        assert result["degraded_files"] == ["bad.py"]
        assert {f["symbol"] for f in result["findings"]} == {"good_orphan"}


# ---------------------------------------------------------------------------
# AC-021: polyglot — ONE call runs ALL matching dialects
# ---------------------------------------------------------------------------


class TestAC021:
    def test_polyglot_single_call_runs_both_dialects(
        self, tmp_worktree: Path
    ) -> None:
        _write(tmp_worktree, "app.py", "def py_orphan():\n    pass\n")
        _write(tmp_worktree, "app.ts", "export class TsOrphan {}\n")

        result = analyze_wiring(["app.py", "app.ts"], tmp_worktree, "FEATURE")

        assert result is not None
        assert set(result["languages"]) == {"python", "typescript"}
        by_symbol = {f["symbol"]: f for f in result["findings"]}
        assert set(by_symbol) == {"py_orphan", "TsOrphan"}
        assert by_symbol["py_orphan"]["language"] == "python"
        assert by_symbol["TsOrphan"]["language"] == "typescript"


# ---------------------------------------------------------------------------
# Status discipline / robustness
# ---------------------------------------------------------------------------


class TestStatusDiscipline:
    def test_absent_vs_empty_are_distinct(self, tmp_worktree: Path) -> None:
        """AC-015 spirit: None (probe didn't run) vs complete-with-empty-
        findings (real positive verdict) are distinct outcomes."""
        absent = analyze_wiring(["app.py"], tmp_worktree, "DOCUMENTATION")
        assert absent is None

        _write(tmp_worktree, "wired.py", "def wired():\n    pass\n")
        _write(tmp_worktree, "user.py", "from wired import wired\nwired()\n")
        positive = analyze_wiring(["wired.py"], tmp_worktree, "FEATURE")
        assert positive is not None
        assert positive["status"] == "complete"
        assert positive["findings"] == []

    def test_unexpected_exception_fails_open_to_error_status(
        self, tmp_worktree: Path
    ) -> None:
        """An unexpected analyzer exception → status:'error', never a raise
        (fail-open to absent-signal at the Coach seam)."""

        class ExplodingStack:
            @property
            def language(self) -> str:
                raise RuntimeError("boom")

        _write(tmp_worktree, "app.py", "def f():\n    pass\n")
        result = analyze_wiring(
            ["app.py"], tmp_worktree, "FEATURE", stack=ExplodingStack()
        )

        assert result is not None
        assert result["status"] == "error"
        assert result["findings"] == []

    def test_result_is_json_serializable(self, tmp_worktree: Path) -> None:
        _write(tmp_worktree, "app.py", "def lonely():\n    pass\n")
        result = analyze_wiring(["app.py"], tmp_worktree, "FEATURE")
        json.dumps(result)

    def test_no_status_maps_to_pass_without_findings_check(
        self, tmp_worktree: Path
    ) -> None:
        """unsupported_stack carries findings:[] but is NOT 'complete' —
        the discriminator a naive findings==[] reader is corrected by."""
        class StackProfile:
            language = "rust"

        _write(tmp_worktree, "lib.rs", "pub fn f() {}\n")
        result = analyze_wiring(
            ["lib.rs"], tmp_worktree, "FEATURE", stack=StackProfile()
        )
        assert result is not None
        assert result["findings"] == [] and result["status"] != "complete"

    def test_dialect_registry_contains_all_four(self) -> None:
        from guardkitfactory.wiring.dialect import get_dialect, iter_dialects

        assert {d.language for d in iter_dialects()} >= {
            "python", "javascript", "typescript", "c_sharp",
        }
        assert get_dialect("ruby") is None
