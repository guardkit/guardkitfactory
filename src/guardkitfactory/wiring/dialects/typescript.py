"""TypeScript wiring dialect descriptor.

Registers the ``WiringDialect`` for TypeScript at import time.
Shares query bodies with JavaScript where grammars overlap.

Note: ``.tsx`` files are parsed with the plain ``typescript`` grammar;
JSX-heavy files will parse-degrade and bias WIRED (recorded in
``degraded_files``), never produce a false UNWIRED.
"""

from __future__ import annotations

from guardkitfactory.wiring.dialect import WiringDialect, register_dialect

dialect = register_dialect(
    WiringDialect(
        language="typescript",
        ts_language_name="typescript",
        file_globs=("**/*.ts", "*.ts", "**/*.tsx", "*.tsx"),
        # Export-wrapped declarations only (scope §3.2).  Class/interface
        # names are (type_identifier) in the TS grammar.
        public_symbols_query="""
            (export_statement
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
