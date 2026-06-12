"""C# wiring dialect descriptor.

Registers the ``WiringDialect`` for C# at import time.

Note the pack key is ``"csharp"`` (NOT ``"c_sharp"``) while the registry
language stays ``"c_sharp"``.
"""

from __future__ import annotations

from guardkitfactory.wiring.dialect import WiringDialect, register_dialect

dialect = register_dialect(
    WiringDialect(
        language="c_sharp",
        ts_language_name="csharp",
        file_globs=("**/*.cs", "*.cs"),
        # Captures @visibility alongside @name; the analyzer pairs them per
        # match and keeps only public/internal (public_visibilities below).
        # Declarations with NO modifier are not captured — invisible symbols
        # bias WIRED, never false-UNWIRED.
        public_symbols_query="""
            [
                (class_declaration
                  (modifier) @visibility
                  name: (identifier) @name)
                (interface_declaration
                  (modifier) @visibility
                  name: (identifier) @name)
                (method_declaration
                  (modifier) @visibility
                  name: (identifier) @name)
            ]
        """,
        references_query="""
            (identifier) @name
        """,
        registration_queries=(
            # .NET DI: services.AddScoped<X>() / AddSingleton<X>() / AddTransient<X>()
            """
            (invocation_expression
              function: (member_access_expression
                name: (generic_name
                  (identifier) @method
                  (type_argument_list
                    (identifier) @target)))
              (#any-of? @method "AddScoped" "AddSingleton" "AddTransient"))
            """,
            # Minimal API: app.MapGet(..., Handler) / MapPost / MapGroup
            """
            (invocation_expression
              function: (member_access_expression
                name: (identifier) @method)
              arguments: (argument_list
                (argument
                  (identifier) @target))
              (#any-of? @method "MapGet" "MapPost" "MapPut" "MapDelete" "MapGroup"))
            """,
            # FastEndpoints reachable-by-convention: public class X : Endpoint<...>
            """
            (class_declaration
              name: (identifier) @target
              (base_list
                [
                  (identifier) @base
                  (generic_name (identifier) @base)
                ])
              (#match? @base "^Endpoint"))
            """,
        ),
        # Moq: new Mock<T>(); NSubstitute: Substitute.For<T>();
        # FakeItEasy: A.Fake<T>().  @target is the generic TYPE argument.
        mock_call_query="""
            (object_creation_expression
              type: (generic_name
                (identifier) @fn
                (type_argument_list
                  (identifier) @target))
              (#eq? @fn "Mock"))
            (invocation_expression
              function: (member_access_expression
                name: (generic_name
                  (identifier) @fn
                  (type_argument_list
                    (identifier) @target)))
              (#any-of? @fn "For" "Fake"))
        """,
        test_path_markers=("Tests/", "Test.cs", "Tests.cs", "/tests/", ".spec.", "_test."),
        acceptance_path_markers=("features/", "tests/integration/", "tests/e2e/"),
        external_mock_allowlist=(
            "HttpClient",
            "ILogger",
            "IConfiguration",
            "HttpMessageHandler",
        ),
        external_mock_path_roots=("Adapters/", "Clients/", "_External/", "External/"),
        script_manifest_files=("*.csproj",),
        public_visibilities=("public", "internal"),
        smoke_snippet="public class SmokeProbe { }\n",
        smoke_expected_symbol="SmokeProbe",
    )
)
