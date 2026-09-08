"""Static declaration versus bounded runtime observation comparison."""

from __future__ import annotations

from contextc.diagnostics import Diagnostic, DiagnosticCode, get_definition
from contextc.live_mcp.models import (
    CapabilityCorrespondenceResult,
    CorrespondenceState,
    LiveToolSnapshot,
    MCPRuntimeObservation,
)


def compare_tool(
    snapshot: LiveToolSnapshot, observation: MCPRuntimeObservation
) -> CapabilityCorrespondenceResult:
    declared = set(snapshot.declared_capabilities)
    observed = set(observation.observed_capabilities)
    unexpected = tuple(sorted(observed - declared, key=str))
    unobserved = tuple(sorted(declared - observed, key=str))
    sensitivity_mismatch = (
        observation.observed_sensitivity is not None
        and snapshot.possible_output_sensitivity is not None
        and observation.observed_sensitivity != snapshot.possible_output_sensitivity
    )
    diagnostics: list[Diagnostic] = []
    if unexpected or sensitivity_mismatch:
        definition = get_definition(DiagnosticCode.MCP_DECLARATION_MISMATCH)
        diagnostics.append(
            Diagnostic(
                code=DiagnosticCode.MCP_DECLARATION_MISMATCH,
                severity=definition.default_severity,
                message=(
                    f"observed MCP behavior for {snapshot.tool_name} exceeds "
                    "or differs from its declaration"
                ),
                node_ids=(snapshot.tool_name,),
                evidence={
                    "undeclared_observed_capabilities": [v.value for v in unexpected],
                    "declared_sensitivity": None
                    if snapshot.possible_output_sensitivity is None
                    else snapshot.possible_output_sensitivity.value,
                    "observed_sensitivity": None
                    if observation.observed_sensitivity is None
                    else observation.observed_sensitivity.value,
                },
                owning_pass="live_mcp_correspondence",
            )
        )
        state = CorrespondenceState.OBSERVED_MISMATCH
    elif unobserved:
        state = CorrespondenceState.DECLARED_BUT_UNOBSERVED
    elif snapshot.declared_capabilities == () and observation.observed_capabilities == ():
        state = CorrespondenceState.UNKNOWN
    else:
        state = CorrespondenceState.OBSERVED_MATCH
    return CapabilityCorrespondenceResult(
        tool_name=snapshot.tool_name,
        declared_capabilities=snapshot.declared_capabilities,
        observed_capabilities=observation.observed_capabilities,
        matched=state is CorrespondenceState.OBSERVED_MATCH,
        state=state,
        undeclared_observed_capabilities=unexpected,
        declared_but_unobserved_capabilities=unobserved,
        declared_sensitivity=snapshot.possible_output_sensitivity,
        observed_sensitivity=observation.observed_sensitivity,
        diagnostics=tuple(diagnostics),
    )
