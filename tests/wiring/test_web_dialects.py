"""TSX / JSX parsing and honest reporting of files no dialect reads (W4).

- ``.tsx`` is read with the pack's ``tsx`` grammar (TypeScript plus JSX); the
  plain ``typescript`` grammar parse-degraded every ``.tsx`` file.
- ``.jsx`` is read by the JavaScript dialect, whose grammar includes JSX.
- An authored source file in a language with no dialect (e.g. ``.go``) is
  listed in ``undialected_files``, and a result that lists one is never
  ``complete``: beside analysed files the status is ``partly_unsupported``;
  alone it stays ``unsupported_stack``.
- No Go wiring analysis is claimed.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from guardkitfactory.wiring import analyze_stub_scan, analyze_wiring


@pytest.fixture()
def tmp_worktree(tmp_path: Path) -> Path:
    """A temporary worktree directory."""
    return tmp_path


def _write(worktree: Path, rel: str, content: str) -> str:
    path = worktree / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return rel


def _react_tsx_app(worktree: Path) -> list[str]:
    """A small React app in TSX; returns the authored files.

    ``Placeholder`` is wired but a stub; ``OrphanBanner`` is exported and
    used nowhere; ``Greeting`` and ``App`` are real and wired.
    """
    authored = [
        _write(
            worktree,
            "web/src/components/Greeting.tsx",
            "type Props = { name: string };\n"
            "export function Greeting({ name }: Props) {\n"
            '  return <p className="greeting">Hello {name}</p>;\n'
            "}\n",
        ),
        _write(
            worktree,
            "web/src/components/Placeholder.tsx",
            "export function Placeholder() {\n"
            "  // TODO: render the summary panel\n"
            "  return null;\n"
            "}\n",
        ),
        _write(
            worktree,
            "web/src/components/OrphanBanner.tsx",
            "export function OrphanBanner() {\n"
            '  return <div role="status">Saved</div>;\n'
            "}\n",
        ),
        _write(
            worktree,
            "web/src/App.tsx",
            'import { Greeting } from "./components/Greeting";\n'
            'import { Placeholder } from "./components/Placeholder";\n'
            "export default function App() {\n"
            "  return (\n"
            "    <main>\n"
            '      <Greeting name="reader" />\n'
            "      <Placeholder />\n"
            "    </main>\n"
            "  );\n"
            "}\n",
        ),
    ]
    # Pre-existing entry point (not authored) that renders App.
    _write(
        worktree,
        "web/src/main.tsx",
        'import { createRoot } from "react-dom/client";\n'
        'import App from "./App";\n'
        'createRoot(document.getElementById("root")!).render(<App />);\n',
    )
    return authored


# ---------------------------------------------------------------------------
# TSX / JSX are parsed, not degraded
# ---------------------------------------------------------------------------


class TestTsxParsing:
    def test_tsx_dialect_uses_tsx_grammar(self) -> None:
        from guardkitfactory.wiring.dialect import _find_language, get_dialect

        tsx = get_dialect("tsx")
        assert tsx is not None
        assert tsx.ts_language_name == "tsx"
        assert tsx.smoke_test() is True
        assert _find_language("tsx") == "tsx"
        assert _find_language("jsx") == "javascript"
        # .ts stays on the plain typescript grammar.
        assert get_dialect("typescript").ts_language_name == "typescript"

    def test_react_tsx_unwired_export_found(self, tmp_worktree: Path) -> None:
        authored = _react_tsx_app(tmp_worktree)

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["degraded_files"] == []
        assert result["undialected_files"] == []
        assert result["languages"] == ["tsx"]
        assert {f["symbol"] for f in result["findings"]} == {"OrphanBanner"}
        json.dumps(result)

    def test_react_tsx_stub_component_found(self, tmp_worktree: Path) -> None:
        authored = _react_tsx_app(tmp_worktree)

        result = analyze_stub_scan(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["degraded_files"] == []
        assert {f["symbol"] for f in result["findings"]} == {"Placeholder"}

    def test_react_jsx_stub_and_unwired_export_found(
        self, tmp_worktree: Path
    ) -> None:
        authored = [
            _write(
                tmp_worktree,
                "web/src/Panel.jsx",
                "export function Panel() {\n  // TODO\n  return null;\n}\n",
            ),
            _write(
                tmp_worktree,
                "web/src/Lonely.jsx",
                "export function LonelyBadge() {\n"
                '  return <span className="badge">1</span>;\n'
                "}\n",
            ),
            _write(
                tmp_worktree,
                "web/src/Page.jsx",
                'import { Panel } from "./Panel";\n'
                "export default function Page() {\n"
                "  return <section><Panel /></section>;\n"
                "}\n",
            ),
        ]
        _write(
            tmp_worktree,
            "web/src/index.jsx",
            'import Page from "./Page";\nrender(<Page />);\n',
        )

        wiring = analyze_wiring(authored, tmp_worktree, "FEATURE")
        stubs = analyze_stub_scan(authored, tmp_worktree, "FEATURE")

        assert wiring is not None and stubs is not None
        assert wiring["status"] == "complete"
        assert wiring["degraded_files"] == []
        assert {f["symbol"] for f in wiring["findings"]} == {"LonelyBadge"}
        assert {f["symbol"] for f in stubs["findings"]} == {"Panel"}

    def test_unparsable_tsx_degraded_and_not_complete(
        self, tmp_worktree: Path
    ) -> None:
        """Only the broken file degrades; the valid TSX beside it is read."""
        authored = _react_tsx_app(tmp_worktree)
        authored.append(
            _write(
                tmp_worktree,
                "web/src/components/Broken.tsx",
                "export function Broken( {\n  return <div>\n",
            )
        )

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")
        stubs = analyze_stub_scan(authored, tmp_worktree, "FEATURE")

        assert result is not None and stubs is not None
        assert result["status"] == "parse_degraded"
        assert result["status"] != "complete"
        assert result["degraded_files"] == ["web/src/components/Broken.tsx"]
        assert {f["symbol"] for f in result["findings"]} == {"OrphanBanner"}
        assert stubs["status"] == "parse_degraded"
        assert stubs["degraded_files"] == ["web/src/components/Broken.tsx"]


# ---------------------------------------------------------------------------
# Files no dialect reads are listed, and the result is never complete
# ---------------------------------------------------------------------------


_GO_HANDLER = (
    "package api\n\n"
    'import "net/http"\n\n'
    "func Health(w http.ResponseWriter, r *http.Request) {}\n"
)


class TestUndialectedFiles:
    def test_mixed_tsx_and_go_lists_go_and_is_not_complete(
        self, tmp_worktree: Path
    ) -> None:
        authored = _react_tsx_app(tmp_worktree)
        authored.append(_write(tmp_worktree, "api/health.go", _GO_HANDLER))
        authored.append(
            _write(tmp_worktree, "api/health_test.go", "package api\n")
        )

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "partly_unsupported"
        assert result["status"] != "complete"
        assert result["undialected_files"] == [
            "api/health.go", "api/health_test.go",
        ]
        assert result["degraded_files"] == []
        # The TSX half is still analysed; nothing is claimed for Go.
        assert result["languages"] == ["tsx"]
        assert {f["symbol"] for f in result["findings"]} == {"OrphanBanner"}
        assert all(f["language"] != "go" for f in result["findings"])
        json.dumps(result)

    def test_mixed_ts_and_go_no_longer_reads_complete(
        self, tmp_worktree: Path
    ) -> None:
        """The silent drop: a clean .ts file beside a .go file used to read
        ``complete`` with empty findings, as if the Go file were checked."""
        _write(tmp_worktree, "web/src/client.ts", "export class ApiClient {}\n")
        _write(
            tmp_worktree,
            "web/src/main.ts",
            'import { ApiClient } from "./client";\nnew ApiClient();\n',
        )
        authored = [
            "web/src/client.ts",
            _write(tmp_worktree, "api/health.go", _GO_HANDLER),
        ]

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")
        stubs = analyze_stub_scan(authored, tmp_worktree, "FEATURE")

        assert result is not None and stubs is not None
        assert result["findings"] == []
        assert result["status"] == "partly_unsupported"
        assert result["undialected_files"] == ["api/health.go"]
        assert stubs["status"] == "partly_unsupported"
        assert stubs["undialected_files"] == ["api/health.go"]

    def test_mixed_with_degraded_keeps_both_lists(
        self, tmp_worktree: Path
    ) -> None:
        authored = [
            _write(tmp_worktree, "web/src/Bad.tsx", "export function Bad( {\n"),
            _write(tmp_worktree, "api/health.go", _GO_HANDLER),
        ]

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "partly_unsupported"
        assert result["degraded_files"] == ["web/src/Bad.tsx"]
        assert result["undialected_files"] == ["api/health.go"]

    def test_go_only_change_under_typescript_stack_is_unsupported(
        self, tmp_worktree: Path
    ) -> None:
        """A stack whose language has a dialect, but a change that touched
        only Go, is unsupported_stack — not a silent None."""

        class StackProfile:
            language = "typescript"

        authored = [_write(tmp_worktree, "api/health.go", _GO_HANDLER)]

        result = analyze_wiring(
            authored, tmp_worktree, "FEATURE", stack=StackProfile()
        )

        assert result is not None
        assert result["status"] == "unsupported_stack"
        assert result["language"] == "go"
        assert result["undialected_files"] == ["api/health.go"]

    def test_go_only_change_lists_files(self, tmp_worktree: Path) -> None:
        authored = [_write(tmp_worktree, "api/health.go", _GO_HANDLER)]

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "unsupported_stack"
        assert result["undialected_files"] == ["api/health.go"]

    def test_non_source_files_are_not_listed(self, tmp_worktree: Path) -> None:
        """Only known source languages count; docs and config do not."""
        authored = _react_tsx_app(tmp_worktree)
        authored.append(_write(tmp_worktree, "README.md", "# app\n"))
        authored.append(_write(tmp_worktree, "web/package.json", "{}\n"))

        result = analyze_wiring(authored, tmp_worktree, "FEATURE")

        assert result is not None
        assert result["status"] == "complete"
        assert result["undialected_files"] == []
