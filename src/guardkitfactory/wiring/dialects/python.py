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
        # ---------------------------------------------------------------------------
        # Anti-stub body scan (TASK-QAV-001)
        # ---------------------------------------------------------------------------
        # Captures module-level function definitions and decorated functions.
        # The analyzer classifies the body as a stub using stub_body_node_types
        # and stub_marker_patterns.  Decorated functions are excluded from
        # stub-flagging to avoid false positives on abstract methods,
        # framework-decorated handlers, etc. (FEAT-C332 bias posture).
        stub_body_query="""
            (function_definition
              name: (identifier) @name
              body: (block) @body)
            (decorated_definition
              definition: (function_definition
                name: (identifier) @name
                body: (block) @body))
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
            "block",
        ),
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
        # Directories that hold source but are not part of the importable
        # module path, so `src/forge/cli/serve.py` is the module
        # `forge.cli.serve`.  Used to tell a call to THIS repo's function from
        # a call to a same-named third-party one.
        source_root_dirs=("src", "lib", "source"),
        # Decorators known not to change what the function accepts.  Anything
        # else (click/typer command builders, framework wrappers) means the
        # `def` line no longer describes how the name is called, so the
        # signature is withheld rather than guessed at.
        signature_preserving_decorators=(
            # stdlib functools
            "cache", "lru_cache", "wraps", "cached_property",
            "singledispatch", "singledispatchmethod", "total_ordering",
            # typing / abc / builtins
            "overload", "final", "override", "no_type_check",
            "runtime_checkable", "abstractmethod", "abstractproperty",
            "staticmethod", "classmethod", "property",
            # dataclasses + contextlib (wrap the RETURN, not the parameters)
            "dataclass", "contextmanager", "asynccontextmanager",
        ),
        # --- WS3-S3 2b CALLSITE_DRIFT + import map -------------------------
        # Whole import nodes; the analyzer walks each to build the per-file
        # import map local_name -> (origin_module, original_name).
        imports_query="""
            (import_statement) @imp
            (import_from_statement) @imp
        """,
        # Module-level function definitions (+ decorated): name @name, params
        # @params.  The ctor-signature query generalized beyond __init__.
        function_signature_query="""
            (module
              (function_definition
                name: (identifier) @name
                parameters: (parameters) @params))
            (module
              (decorated_definition
                definition: (function_definition
                  name: (identifier) @name
                  parameters: (parameters) @params)))
        """,
        # Call sites: bare-identifier callee `fn(...)` OR attribute callee
        # `base.fn(...)`.  The analyzer resolves attribute callees only when
        # `base` denotes a module binding (R2b-8); v1 processes bare-identifier
        # callees (functions + `ClassName(...)` ctors).
        call_site_query="""
            (call
              function: (identifier) @callee
              arguments: (argument_list) @args)
            (call
              function: (attribute
                attribute: (identifier) @callee)
              arguments: (argument_list) @args)
        """,
        # --- 2a signature-binding-fake scan (§2) ---------------------------
        # Test-file function/class/lambda definitions that may be permissive
        # doubles. The analyzer classifies against the permissiveness ladder.
        double_def_query="""
            (function_definition
              name: (identifier) @name
              parameters: (parameters) @params
              body: (block) @body)
            (class_definition
              name: (identifier) @cname
              body: (block) @cbody)
        """,
        double_name_affixes=(
            "Fake", "Stub", "Spy", "Double", "Mock", "Dummy", "Noop", "Null", "InMemory",
        ),
        bind_escape_patterns=(".bind(", "SignatureBindingFake"),
        binding_kwarg_names=("autospec", "wraps"),
        binding_ctor_names=("create_autospec",),
        # --- ENVTAMPER-a skip-guard extraction (§5.1.1) --------------------
        # pytest.importorskip("X") and find_spec("X") literal-arg calls; the
        # analyzer collects the string module arg. HAS_X = try-import and
        # computed names are accepted FNs (documented).
        skip_guard_query="""
            (call
              function: [
                (identifier) @fn
                (attribute attribute: (identifier) @fn)
              ]
              arguments: (argument_list
                .
                (string) @modarg)
              (#any-of? @fn "importorskip" "find_spec"))
        """,
        # --- ENVTAMPER-b product-file sys.modules tamper (§5.2) ------------
        # Capture the mutation containers + the `<recv>.modules` receiver
        # attribute (@recv) and, for calls, the method + args. The analyzer
        # owns receiver resolution (is `<recv>` the `sys` module, direct or
        # aliased?) via the import map, and the FP posture (self-replacement,
        # alias shim, del cache-bust). Also the from-import `modules[...]` form
        # via a bare-identifier receiver (@recv_id).
        env_tamper_query="""
            (assignment
              left: (subscript
                value: (attribute) @recv)) @assign
            (assignment
              left: (subscript
                value: (identifier) @recv_id)) @assign
            (delete_statement
              (subscript
                value: (attribute) @recv)) @del
            (delete_statement
              (subscript
                value: (identifier) @recv_id)) @del
            (call
              function: (attribute
                object: (attribute) @recv
                attribute: (identifier) @method)
              arguments: (argument_list) @cargs) @call
            (call
              function: (attribute
                object: (identifier) @recv_id
                attribute: (identifier) @method)
              arguments: (argument_list) @cargs) @call
        """,
    )
)
