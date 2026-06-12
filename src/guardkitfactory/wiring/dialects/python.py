"""Python wiring dialect descriptor.

Registers the ``WiringDialect`` for Python at import time.
"""

from __future__ import annotations

from guardkitfactory.wiring.dialect import WiringDialect, register_dialect

dialect = register_dialect(
    WiringDialect(
        language="python",
        ts_language_name="python",
        file_globs=("**/*.py", "*.py"),
        # Module-level defs/classes, including decorated ones.  Privacy is
        # handled by private_name_prefixes ("_") in the analyzer.
        public_symbols_query="""
            (module
              [
                (function_definition
                  name: (identifier) @name)
                (class_definition
                  name: (identifier) @name)
                (decorated_definition
                  definition: [
                    (function_definition
                      name: (identifier) @name)
                    (class_definition
                      name: (identifier) @name)
                  ])
              ])
        """,
        # Blanket identifier capture: with the analyzer excluding the
        # defining file and test files from the reference map, any
        # occurrence of the name elsewhere counts as a reference
        # (biased WIRED per the scope's FP/FN posture).
        references_query="""
            (identifier) @name
        """,
        registration_queries=(
            # Click / FastAPI / generic registries:
            #   cli.add_command(X), api.include_router(X), registry.register(X)
            """
            (call
              function: (attribute
                attribute: (identifier) @method)
              arguments: (argument_list
                (identifier) @target)
              (#any-of? @method "add_command" "include_router" "register"))
            """,
            # Decorator-registered commands/routes:
            #   @cli.command() / @app.get("/x") above a def
            """
            (decorated_definition
              (decorator
                (call
                  function: (attribute
                    attribute: (identifier) @method)
                  (#any-of? @method "command" "route" "get" "post" "put" "delete")))
              definition: (function_definition
                name: (identifier) @target))
            """,
        ),
        # Restricted to actual mock primitives via predicate:
        #   patch("..."), mock.patch("..."), mocker.patch("..."),
        #   monkeypatch.setattr(target, ...), patch.object(Target, ...)
        mock_call_query="""
            (call
              function: [
                (identifier) @fn
                (attribute
                  attribute: (identifier) @fn)
              ]
              arguments: (argument_list
                .
                [
                  (string) @target
                  (identifier) @target
                ])
              (#any-of? @fn "patch" "setattr" "object"))
        """,
        test_path_markers=("/test_", "_test.", ".test.", "/tests/", "conftest.py"),
        acceptance_path_markers=("features/", "tests/integration/", "tests/e2e/"),
        external_mock_allowlist=("httpx", "requests", "boto3", "openai", "sqlalchemy"),
        external_mock_path_roots=("adapters/", "clients/", "_external/", "external/"),
        script_manifest_files=("pyproject.toml", "setup.py", "setup.cfg"),
        private_name_prefixes=("_",),
        smoke_snippet="def smoke_probe():\n    pass\n",
        smoke_expected_symbol="smoke_probe",
    )
)
