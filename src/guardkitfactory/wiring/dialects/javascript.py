"""JavaScript wiring dialect descriptor.

Registers the ``WiringDialect`` for JavaScript at import time.
"""

from __future__ import annotations

from guardkitfactory.wiring.dialect import WiringDialect, register_dialect

dialect = register_dialect(
    WiringDialect(
        language="javascript",
        ts_language_name="javascript",
        file_globs=("**/*.js", "*.js", "**/*.mjs", "*.mjs", "**/*.cjs", "*.cjs"),
        # Export-wrapped declarations only: an unexported top-level symbol
        # is module-private, not a wiring candidate (scope §3.2).
        public_symbols_query="""
            (export_statement
              [
                (function_declaration
                  name: (identifier) @name)
                (class_declaration
                  name: (identifier) @name)
                (lexical_declaration
                  (variable_declarator
                    name: (identifier) @name))
                (variable_declaration
                  (variable_declarator
                    name: (identifier) @name))
              ])
        """,
        references_query="""
            (identifier) @name
        """,
        registration_queries=(
            # Express / routers / generic registries:
            #   app.use(X), router.get('/x', handler), registry.register(X)
            """
            (call_expression
              function: (member_expression
                property: (property_identifier) @method)
              arguments: (arguments
                (identifier) @target)
              (#any-of? @method "use" "get" "post" "put" "delete" "register"))
            """,
        ),
        # jest.mock('...'), vi.mock('...'), sinon.stub(obj, 'm'),
        # jest.spyOn(obj, 'm') — restricted via predicate.
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
        external_mock_allowlist=("axios", "fetch", "node-fetch", "express"),
        external_mock_path_roots=("adapters/", "clients/", "_external/", "external/"),
        script_manifest_files=("package.json",),
        smoke_snippet="export function smokeProbe() {}\n",
        smoke_expected_symbol="smokeProbe",
    )
)
