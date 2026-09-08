"""M9 structural security analysis and policy application."""

from __future__ import annotations

from contextc.diagnostics import Diagnostic, DiagnosticCode, Severity
from contextc.hashing import semantic_hash
from contextc.ir import ContextGraph, ContextNode, InstructionAuthority, Sensitivity
from contextc.security.models import (
    PolicyAction,
    SecurityDecision,
    SecurityPolicy,
    SecurityResult,
    SecurityRule,
    TaintLimits,
    TaintPath,
)
from contextc.security.patterns import detect_instruction_signals
from contextc.security.policy import policy_identity
from contextc.security.taint import find_taint_paths
from contextc.security.transform import quote_as_data, redact

ANALYSIS_VERSION = "m9-security-v1"


def _sink_kind(node: ContextNode) -> str:
    value = node.metadata.get("security_sink")
    return str(value) if isinstance(value, str) else ""


def _diagnostic(
    code: DiagnosticCode,
    node_ids: tuple[str, ...],
    message: str,
    evidence: dict[str, object],
) -> Diagnostic:
    severity = (
        Severity.ERROR
        if code
        in {
            DiagnosticCode.SENSITIVITY_POLICY_VIOLATION,
            DiagnosticCode.UNTRUSTED_INSTRUCTION_SCOPE,
            DiagnosticCode.SENSITIVE_EXTERNAL_FLOW,
        }
        else Severity.WARNING
    )
    return Diagnostic(
        code=code,
        severity=severity,
        message=message,
        node_ids=node_ids,
        evidence=evidence,
        owning_pass="security_analysis",
    )


def _rule_diagnostic(
    *, node: ContextNode, rule_id: str, diagnostic_code: str | None
) -> Diagnostic | None:
    if diagnostic_code is None:
        return None
    try:
        code = DiagnosticCode(diagnostic_code)
    except ValueError:
        return None
    if code in {
        DiagnosticCode.UNTRUSTED_INSTRUCTION_SCOPE,
        DiagnosticCode.SENSITIVE_EXTERNAL_FLOW,
    }:
        return None
    if code is DiagnosticCode.SENSITIVITY_POLICY_VIOLATION:
        return _diagnostic(
            code,
            (node.node_id,),
            "Content violates the active sensitivity policy.",
            {
                "rule_id": rule_id,
                "source_uri": node.source.uri,
                "sensitivity": node.sensitivity.value,
            },
        )
    return _diagnostic(
        code,
        (node.node_id,),
        "Security policy rule matched.",
        {"rule_id": rule_id, "source_uri": node.source.uri},
    )


def _matching_local_rules(
    node: ContextNode,
    *,
    signal_categories: frozenset[str],
    policy: SecurityPolicy,
) -> list[SecurityRule]:
    candidates: list[SecurityRule] = []
    for rule in policy.rules:
        if not rule.enabled:
            continue
        if not (
            rule.source_domains or rule.sensitivities or rule.signal_categories or rule.sink_kinds
        ):
            continue
        if rule.source_domains and node.trust_domain not in rule.source_domains:
            continue
        if rule.sensitivities and node.sensitivity not in rule.sensitivities:
            continue
        if rule.signal_categories and not signal_categories.intersection(rule.signal_categories):
            continue
        if rule.sink_kinds and _sink_kind(node) not in rule.sink_kinds:
            continue
        candidates.append(rule)
    return candidates


def analyze_security(
    graph: ContextGraph,
    policy: SecurityPolicy,
    *,
    limits: TaintLimits | None = None,
) -> SecurityResult:
    limits = TaintLimits() if limits is None else limits
    nodes = {node.node_id: node for node in graph.nodes}
    signals = {node.node_id: detect_instruction_signals(node) for node in graph.nodes}
    instruction_sinks = tuple(
        node.node_id for node in graph.nodes if _sink_kind(node) in policy.instruction_sink_kinds
    )
    external_sinks = tuple(
        node.node_id for node in graph.nodes if _sink_kind(node) in policy.external_sink_kinds
    )
    untrusted_sources = tuple(
        node.node_id
        for node in graph.nodes
        if node.trust_domain in policy.untrusted_domains and signals[node.node_id]
    )
    sensitive_sources = tuple(
        node.node_id
        for node in graph.nodes
        if node.sensitivity in {Sensitivity.SENSITIVE, Sensitivity.SECRET}
    )
    instruction_paths = find_taint_paths(
        graph,
        source_node_ids=untrusted_sources,
        sink_node_ids=instruction_sinks,
        rule_id="untrusted-instruction-flow",
        limits=limits,
    )
    sensitive_paths = find_taint_paths(
        graph,
        source_node_ids=sensitive_sources,
        sink_node_ids=external_sinks,
        rule_id="sensitive-external-flow",
        limits=limits,
    )

    path_by_source: dict[tuple[str, str], TaintPath] = {}
    for taint_path in instruction_paths + sensitive_paths:
        path_by_source[(taint_path.rule_id, taint_path.source_node_id)] = taint_path

    diagnostics: list[Diagnostic] = []
    decisions: list[SecurityDecision] = []
    transformed = dict(nodes)
    excluded: set[str] = set()
    blocked: set[str] = set()

    for node_id in sorted(nodes):
        node = nodes[node_id]
        node_signals = signals[node_id]
        categories = frozenset(signal.category for signal in node_signals)
        if node_signals:
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.INJECTION_RISK_SIGNAL,
                    (node_id,),
                    "Instruction-like security signal detected.",
                    {
                        "signal_categories": tuple(signal.category for signal in node_signals),
                        "source_uri": node.source.uri,
                    },
                )
            )
        override_categories = {
            "claim_higher_authority",
            "override_prior_instructions",
            "change_privileged_policy",
        }
        if node.instruction_authority is InstructionAuthority.NONE and categories.intersection(
            override_categories
        ):
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.TRUST_AUTHORITY_OVERRIDE,
                    (node_id,),
                    "Content attempts to claim or override a higher authority boundary.",
                    {
                        "source_uri": node.source.uri,
                        "trust_domain": node.trust_domain.value,
                        "instruction_authority": node.instruction_authority.value,
                    },
                )
            )

        candidates = _matching_local_rules(
            node,
            signal_categories=categories,
            policy=policy,
        )
        instruction_key = ("untrusted-instruction-flow", node_id)
        if instruction_key in path_by_source:
            candidates.extend(
                rule
                for rule in policy.rules
                if rule.rule_id == "untrusted-instruction-flow" and rule not in candidates
            )
            instruction_path = path_by_source[instruction_key]
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.UNTRUSTED_INSTRUCTION_SCOPE,
                    (node_id, instruction_path.sink_node_id),
                    "Untrusted instruction-like content can flow to an instruction sink.",
                    {
                        "rule_id": "untrusted-instruction-flow",
                        "source_uri": node.source.uri,
                        "path_node_ids": instruction_path.node_ids,
                    },
                )
            )

        sensitive_key = ("sensitive-external-flow", node_id)
        if sensitive_key in path_by_source:
            candidates.extend(
                rule
                for rule in policy.rules
                if rule.rule_id == "sensitive-external-flow" and rule not in candidates
            )
            sensitive_taint_path = path_by_source[sensitive_key]
            diagnostics.append(
                _diagnostic(
                    DiagnosticCode.SENSITIVE_EXTERNAL_FLOW,
                    (node_id, sensitive_taint_path.sink_node_id),
                    "Sensitive content can flow to an external sink.",
                    {
                        "rule_id": "sensitive-external-flow",
                        "source_uri": node.source.uri,
                        "sensitivity": node.sensitivity.value,
                        "path_node_ids": sensitive_taint_path.node_ids,
                    },
                )
            )

        for rule in sorted(candidates, key=lambda item: item.rule_id):
            decision_path = path_by_source.get((rule.rule_id, node_id))
            decisions.append(
                SecurityDecision(
                    node_id=node_id,
                    rule_id=rule.rule_id,
                    action=rule.action,
                    diagnostic_code=rule.diagnostic_code,
                    reason=f"policy rule {rule.rule_id} matched",
                    taint_path=decision_path,
                )
            )
            rule_diagnostic = _rule_diagnostic(
                node=node,
                rule_id=rule.rule_id,
                diagnostic_code=rule.diagnostic_code,
            )
            if rule_diagnostic is not None:
                diagnostics.append(rule_diagnostic)
            if rule.action is PolicyAction.QUOTE_AS_DATA:
                transformed[node_id] = quote_as_data(transformed[node_id], rule.rule_id)
            elif rule.action is PolicyAction.REDACT:
                transformed[node_id] = redact(transformed[node_id], rule.rule_id)
            elif rule.action is PolicyAction.EXCLUDE:
                excluded.add(node_id)
            elif rule.action in {
                PolicyAction.BLOCK_COMPILATION,
                PolicyAction.REQUIRE_EXPLICIT_ALLOW,
            }:
                blocked.add(node_id)

    visible_nodes = tuple(
        transformed[node_id] for node_id in sorted(transformed) if node_id not in excluded
    )
    transformations = {
        node.node_id: node.transformations for node in visible_nodes if node.transformations
    }
    unique_diagnostics = {
        (
            diagnostic.code.value,
            diagnostic.node_ids,
            diagnostic.message,
            semantic_hash(diagnostic.evidence),
        ): diagnostic
        for diagnostic in diagnostics
    }
    return SecurityResult(
        policy_id=policy.policy_id,
        policy_version=policy.version,
        policy_identity=policy_identity(policy),
        analysis_version=ANALYSIS_VERSION,
        nodes=visible_nodes,
        diagnostics=tuple(
            sorted(
                unique_diagnostics.values(),
                key=lambda diagnostic: (
                    diagnostic.code.value,
                    diagnostic.node_ids,
                    diagnostic.message,
                ),
            )
        ),
        decisions=tuple(
            sorted(
                decisions,
                key=lambda decision: (
                    decision.node_id,
                    decision.rule_id,
                    decision.action.value,
                ),
            )
        ),
        taint_paths=tuple(
            sorted(
                instruction_paths + sensitive_paths,
                key=lambda path: (
                    path.rule_id,
                    path.source_node_id,
                    path.sink_node_id,
                    path.node_ids,
                ),
            )
        ),
        excluded_node_ids=tuple(sorted(excluded)),
        blocked_node_ids=tuple(sorted(blocked)),
        transformations=transformations,
        blocked=bool(blocked),
    )
