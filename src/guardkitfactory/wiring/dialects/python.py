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
        # Restricted to actual mock primitives via predicate.  Three families:
        #   1. patch("..."), mock.patch("..."), mocker.patch("..."),
        #      monkeypatch.setattr(target, ...), patch.object(Target, ...)
        #   2. spec-mock constructors: AsyncMock(spec=Service),
        #      MagicMock(spec=Service), Mock(spec_set=Service), ... (AC#2)
        #   3. create_autospec(Service)  (AC#2)
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

            (call
              function: (identifier) @ctor
              arguments: (argument_list
                (keyword_argument
                  name: (identifier) @kw
                  value: [
                    (identifier) @target
                    (attribute) @target
                  ]))
              (#any-of? @ctor
                "Mock" "MagicMock" "AsyncMock"
                "NonCallableMock" "NonCallableMagicMock")
              (#any-of? @kw "spec" "spec_set"))

            (call
              function: (identifier) @autospec
              arguments: (argument_list
                .
                [
                  (identifier) @target
                  (attribute) @target
                ])
              (#eq? @autospec "create_autospec"))
        """,
        test_path_markers=("/test_", "_test.", ".test.", "/tests/", "conftest.py"),
        acceptance_path_markers=("features/", "tests/integration/", "tests/e2e/"),
        external_mock_allowlist=("httpx", "requests", "boto3", "openai", "sqlalchemy"),
        external_mock_path_roots=("adapters/", "clients/", "_external/", "external/"),
        script_manifest_files=("pyproject.toml", "setup.py", "setup.cfg"),
        private_name_prefixes=("_",),
        smoke_snippet="def smoke_probe():\n    pass\n",
        smoke_expected_symbol="smoke_probe",
        # --- CTOR_ARITY probe (composition-root constructor-arity) ----------
        composition_root_markers=(
            "/main.py",
            "main.py",
            "__main__.py",
            "/app.py",
            "app.py",
            "/factory",
            "container",
            "/wiring",
            "/di/",
            "/bootstrap",
        ),
        # A class whose body defines __init__: capture the class @class and
        # the __init__ parameter list @params (per-match pairing).
        constructor_signature_query="""
            (class_definition
              name: (identifier) @class
              body: (block
                (function_definition
                  name: (identifier) @method
                  parameters: (parameters) @params
                  (#eq? @method "__init__"))))
        """,
        # A direct constructor call `ClassName(...)`: bare-identifier callee
        # only (attribute-qualified calls like `mod.ClassName(...)` are an
        # accepted false-negative — bias toward no-finding).
        constructor_call_query="""
            (call
              function: (identifier) @class
              arguments: (argument_list) @args)
        """,
        param_self_names=("self", "cls"),
        param_default_node_types=("default_parameter", "typed_default_parameter"),
        param_splat_node_types=("list_splat_pattern", "dictionary_splat_pattern"),
        param_required_node_types=("identifier", "typed_parameter"),
        arg_keyword_node_types=("keyword_argument",),
        arg_splat_node_types=("list_splat", "dictionary_splat"),
    )
)
