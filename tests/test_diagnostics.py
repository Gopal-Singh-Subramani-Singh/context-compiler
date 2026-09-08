from contextc.diagnostics import (
    REGISTRY,
    Diagnostic,
    DiagnosticCode,
    Severity,
    get_definition,
)


def test_registry_is_authoritative_and_complete() -> None:
    assert set(REGISTRY) == set(DiagnosticCode)
    definition = get_definition(DiagnosticCode.MISSING_DEPENDENCY)
    assert definition.owning_component == "dependency_analysis"
    assert definition.may_continue is False


def test_diagnostic_serialization_preserves_structured_evidence() -> None:
    diagnostic = Diagnostic(
        code=DiagnosticCode.SOURCE_PARSE_FAILED,
        severity=Severity.WARNING,
        message="parse failed",
        node_ids=("node-1",),
        evidence={"line": 3, "facts": ["syntax"]},
        owning_pass="repository_parser",
        suggested_action="repair syntax",
    )
    value = diagnostic.to_dict()
    assert value["code"] == "CTX003"
    assert value["evidence"] == {"facts": ["syntax"], "line": 3}
