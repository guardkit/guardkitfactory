"""TypeScript wiring dialect descriptor.

Registers the ``WiringDialect`` for TypeScript at import time.
Shares query bodies with JavaScript where grammars overlap.

Also registers a ``tsx`` dialect: the same query bodies run over the
pack's ``tsx`` grammar, which is the TypeScript grammar plus JSX.  The plain
``typescript`` grammar cannot read JSX, so a ``.tsx`` file parsed with it
used to parse-degrade every time.  JSX element names (``<Card />``) are
``identifier`` nodes in the ``tsx`` grammar, so the shared references query
already counts a component used as an element as a reference.

Limits: ``.ts`` and ``.tsx`` are separate dialects, so each builds its own
reference map; a symbol defined in one and used only in the other is found
by the raw-text fallback (biased WIRED), not by the reference map, and an
acceptance test in one does not count as mocking a seam authored in the
other.  Arrow-function components (``export const X = () => ...``) are
public symbols but are not stub-scanned, as for ``.ts``.
"""

from __future__ import annotations

from dataclasses import replace

from guardkitfactory.wiring.dialect import WiringDialect, register_dialect

dialect = register_dialect(
    WiringDialect(
        language="typescript",
        ts_language_name="typescript",
        file_globs=(
            "**/*.ts", "*.ts", "**/*.mts", "*.mts", "**/*.cts", "*.cts",
        ),
        # Export-wrapped declarations only (scope §3.2).  Class/interface
        # names are (type_identifier) in the TS grammar.  ``@default_export``
        # marks ``export default``: the importer picks its own local name
        # (``import Home from "./pages/index"``, ``lazy(() => import(...))``),
        # so the declared name is examined but never an UNWIRED candidate.
        public_symbols_query="""
            (export_statement
              "default"? @default_export
              [
                (function_declaration
                  name: (identifier) @name)
                (class_declaration
                  name: (type_identifier) @name)
                (interface_declaration
                  name: (type_identifier) @name)
                (lexical_declaration
                  (variable_declarator
                    name: (identifier) @name))
              ])
        """,
        # ---------------------------------------------------------------------------
        # Anti-stub body scan (TASK-QAV-001)
        # ---------------------------------------------------------------------------
        # Captures exported function declarations and class methods.
        # The analyzer classifies the body as a stub using stub_body_node_types
        # and stub_marker_patterns.
        stub_body_query="""
            (export_statement
              (function_declaration
                name: (identifier) @name
                body: (statement_block) @body))
            (class_declaration
              body: (class_body
                [
                  (method_definition
                    name: (property_identifier) @name
                    body: (statement_block) @body)
                ]))
        """,
        stub_marker_patterns=(
            "TODO",
            "FIXME",
            "STUB",
            "placeholder",
            "HACK",
            "XXX",
        ),
        stub_body_node_types=(
            "statement_block",   # empty block `{}`
        ),
        # Type positions use (type_identifier); value positions (identifier).
        references_query="""
            [
              (identifier)
              (type_identifier)
            ] @name
        """,
        registration_queries=(
            # Express / routers / generic registries
            """
            (call_expression
              function: (member_expression
                property: (property_identifier) @method)
              arguments: (arguments
                (identifier) @target)
              (#any-of? @method "use" "get" "post" "put" "delete" "register"))
            """,
        ),
        mock_call_query="""
            (call_expression
              function: [
                (identifier) @fn
                (member_expression
                  property: (property_identifier) @fn)
              ]
              arguments: (arguments
                .
                [
                  (string) @target
                  (identifier) @target
                ])
              (#any-of? @fn "mock" "doMock" "stub" "spyOn" "fake"))
        """,
        test_path_markers=(
            "/test_", ".test.", ".spec.", "_test.", "/tests/", "/test/", "__tests__/",
        ),
        acceptance_path_markers=("features/", "tests/integration/", "tests/e2e/", "/e2e/"),
        external_mock_allowlist=("axios", "fetch", "node-fetch", "express", "@angular/core"),
        external_mock_path_roots=("adapters/", "clients/", "_external/", "external/"),
        script_manifest_files=("package.json",),
        smoke_snippet="export class SmokeProbe {}\n",
        smoke_expected_symbol="SmokeProbe",
    )
)

# Same DATA, read with the grammar that understands JSX.
tsx_dialect = register_dialect(
    replace(
        dialect,
        language="tsx",
        ts_language_name="tsx",
        file_globs=("**/*.tsx", "*.tsx"),
        # JSX in the snippet: the plain typescript grammar would not read it.
        smoke_snippet="export function SmokeProbe() { return <div />; }\n",
    )
)
