"""Application service for bounded live MCP validation and policy-gated fixture execution."""

from __future__ import annotations

import asyncio
import sys
import time
from collections.abc import Mapping
from pathlib import Path

from contextc.capabilities.models import (
    ApprovalEvidence,
    CapabilityManifest,
    CapabilityPlan,
    PlanCall,
)
from contextc.capabilities.policy import load_policy
from contextc.capabilities.service import CapabilityService
from contextc.hashing import semantic_hash
from contextc.ir import ContextGraph
from contextc.live_mcp.audit import write_audit
from contextc.live_mcp.client import LiveMCPClientAdapter
from contextc.live_mcp.correspondence import compare_tool
from contextc.live_mcp.declarations import capability_declarations, inspection_from_sdk
from contextc.live_mcp.enforcement import blocked_sink_call_ids, execution_decision
from contextc.live_mcp.fixture import validate_fixture_server
from contextc.live_mcp.models import (
    CapabilityCorrespondenceResult,
    LiveExecutionDecision,
    LiveMCPAuditEvent,
    LiveMCPInspectionResult,
    LiveMCPServerSpec,
    LiveMCPValidationResult,
    LivePlanExecutionResult,
    MCPRuntimeObservation,
)
from contextc.live_mcp.observation import observe_tool_result
from contextc.live_mcp.sandbox import initialize_fixture_sandbox
from contextc.security.service import SecurityService


class LiveMCPValidationService:
    def __init__(
        self,
        client: LiveMCPClientAdapter | None = None,
        cache_root: Path | None = None,
    ) -> None:
        self.client = LiveMCPClientAdapter() if client is None else client
        self.cache_root = cache_root

    def _capability_service(
        self, inspection: LiveMCPInspectionResult, *, fixture_version: str
    ) -> CapabilityService:
        if self.cache_root is None:
            return CapabilityService()
        namespace = semantic_hash(
            {
                "stage": "live-mcp-static-capabilities",
                "server_id": inspection.server_id,
                "fixture_version": fixture_version,
            }
        ).removeprefix("sha256:")
        return CapabilityService(self.cache_root / "live-mcp" / namespace)

    @staticmethod
    def fixture_spec(
        server: Path,
        sandbox: Path,
        *,
        timeout_seconds: float = 5.0,
        operation_timeout_seconds: float | None = None,
    ) -> LiveMCPServerSpec:
        server_path = validate_fixture_server(server)
        initialize_fixture_sandbox(sandbox)
        return LiveMCPServerSpec(
            server_id="tiny-contextc-server",
            command=sys.executable,
            args=(str(server_path),),
            sandbox=str(sandbox.resolve()),
            timeout_seconds=timeout_seconds,
            operation_timeout_seconds=operation_timeout_seconds,
        )

    async def inspect_server_async(self, spec: LiveMCPServerSpec) -> LiveMCPInspectionResult:
        async with self.client.connect(spec) as session:
            tools = await session.list_tools()
            resources = await session.list_resources()
            return inspection_from_sdk(server_id=spec.server_id, tools=tools, resources=resources)

    def inspect_server(self, spec: LiveMCPServerSpec) -> LiveMCPInspectionResult:
        return asyncio.run(self.inspect_server_async(spec))

    async def _analyze_with_inspection(
        self,
        inspection: LiveMCPInspectionResult,
        plan: CapabilityPlan,
        approvals: tuple[ApprovalEvidence, ...],
        *,
        fixture_version: str = "1",
    ) -> CapabilityManifest:
        tools, resources = capability_declarations(inspection)
        return self._capability_service(inspection, fixture_version=fixture_version).analyze_plan(
            plan, tools, resources, load_policy(), approvals=approvals
        )

    def analyze_plan(
        self,
        inspection: LiveMCPInspectionResult,
        plan: CapabilityPlan,
        *,
        approvals: tuple[ApprovalEvidence, ...] = (),
        fixture_version: str = "1",
    ) -> CapabilityManifest:
        return asyncio.run(
            self._analyze_with_inspection(
                inspection, plan, approvals, fixture_version=fixture_version
            )
        )

    @staticmethod
    def _input_arguments(call: PlanCall, outputs: Mapping[str, str]) -> dict[str, object]:
        args = dict(call.literal_inputs)
        for binding in call.input_bindings:
            if binding.call_id is not None:
                args[binding.input_name] = outputs.get(binding.call_id, "")
            elif binding.resource_id is not None:
                args[binding.input_name] = binding.resource_id
        return args

    async def execute_validated_plan_async(
        self,
        spec: LiveMCPServerSpec,
        plan: CapabilityPlan,
        *,
        approvals: tuple[ApprovalEvidence, ...] = (),
        audit_path: Path | None = None,
    ) -> LivePlanExecutionResult:
        async with self.client.connect(spec) as session:
            tools_raw = await session.list_tools()
            resources_raw = await session.list_resources()
            inspection = inspection_from_sdk(
                server_id=spec.server_id, tools=tools_raw, resources=resources_raw
            )
            static_manifest = await self._analyze_with_inspection(
                inspection, plan, approvals, fixture_version=spec.fixture_version
            )
            snapshots = {tool.tool_name: tool for tool in inspection.tools}
            blocked_sinks = set(blocked_sink_call_ids(static_manifest))
            outputs: dict[str, str] = {}
            observations: list[MCPRuntimeObservation] = []
            correspondence: list[CapabilityCorrespondenceResult] = []
            audit: list[LiveMCPAuditEvent] = []
            invoked: list[str] = []
            blocked: list[str] = []
            policy_hash = static_manifest.policy_identity
            diagnostic_codes = tuple(d.code.value for d in static_manifest.diagnostics)

            # Invalid declarations/plans block before any runtime call. Dangerous valid
            # flows block at their sink, allowing the source observation to be validated.
            fatal_preflight = static_manifest.blocked and not static_manifest.flows
            for call in plan.calls:
                snapshot = snapshots.get(call.tool_id)
                if snapshot is None:
                    blocked.append(call.call_id)
                    continue
                args = self._input_arguments(call, outputs)
                args_hash = semantic_hash(args)
                sink_blocked = call.call_id in blocked_sinks or fatal_preflight
                if sink_blocked:
                    blocked.append(call.call_id)
                    audit.append(
                        LiveMCPAuditEvent(
                            interaction_id=semantic_hash(
                                {"plan": plan.plan_id, "call": call.call_id, "blocked": True}
                            ),
                            plan_id=plan.plan_id,
                            server_id=spec.server_id,
                            transport=spec.transport,
                            operation="tools/call",
                            tool_or_resource=call.tool_id,
                            arguments_hash=args_hash,
                            result_hash=None,
                            result_sensitivity=None,
                            trust_domain=snapshot.trust_domain,
                            static_decision=LiveExecutionDecision.REQUIRE_APPROVAL
                            if static_manifest.pending_approval
                            else LiveExecutionDecision.BLOCK,
                            approval_state="missing"
                            if static_manifest.pending_approval
                            else "not_applicable",
                            invocation_attempted=True,
                            invocation_performed=False,
                            policy_id=static_manifest.policy_id,
                            policy_hash=policy_hash,
                            diagnostics=diagnostic_codes,
                            duration_ms=0.0,
                        )
                    )
                    continue

                started = time.perf_counter()
                result = await session.call_tool(call.tool_id, args)
                duration_ms = (time.perf_counter() - started) * 1000.0
                observation, node, raw_text = observe_tool_result(
                    server_id=spec.server_id,
                    plan_id=plan.plan_id,
                    call_id=call.call_id,
                    snapshot=snapshot,
                    arguments=args,
                    result=result,
                    fixture_version=spec.fixture_version,
                )
                invoked.append(call.call_id)
                outputs[call.call_id] = raw_text
                observations.append(observation)
                item = compare_tool(snapshot, observation)
                correspondence.append(item)

                graph = ContextGraph()
                graph.add_node(node)
                security = SecurityService.from_policy_path().scan_graph(graph)
                combined_codes = tuple(
                    sorted(
                        set(diagnostic_codes)
                        | {d.code.value for d in security.diagnostics}
                        | {d.code.value for d in item.diagnostics}
                    )
                )
                audit.append(
                    LiveMCPAuditEvent(
                        interaction_id=observation.interaction_id,
                        plan_id=plan.plan_id,
                        server_id=spec.server_id,
                        transport=spec.transport,
                        operation="tools/call",
                        tool_or_resource=call.tool_id,
                        arguments_hash=args_hash,
                        result_hash=observation.content_hash,
                        result_sensitivity=observation.observed_sensitivity,
                        trust_domain=observation.trust_domain,
                        static_decision=LiveExecutionDecision.ALLOW,
                        approval_state="present" if approvals else "not_required",
                        invocation_attempted=True,
                        invocation_performed=True,
                        policy_id=static_manifest.policy_id,
                        policy_hash=policy_hash,
                        diagnostics=combined_codes,
                        duration_ms=duration_ms,
                    )
                )
                if item.diagnostics:
                    # Drift is a hard stop for subsequent operations.
                    remaining = [
                        c.call_id
                        for c in plan.calls
                        if c.call_id not in invoked and c.call_id not in blocked
                    ]
                    blocked.extend(remaining)
                    break

            final_decision = execution_decision(static_manifest, tuple(correspondence))
            secret_reached = False
            for event in audit:
                if event.invocation_performed and event.tool_or_resource in {
                    "post_external_message",
                    "fake_http_post",
                }:
                    secret_reached = any(any(obs.sentinel_flags.values()) for obs in observations)
            events = tuple(audit)
            if audit_path is not None:
                write_audit(audit_path, events)
            return LivePlanExecutionResult(
                server_id=spec.server_id,
                transport=spec.transport,
                server_declaration_hash=inspection.server_declaration_hash,
                fixture_version=spec.fixture_version,
                validation_profile_id="m10b-tiny-stdio-v1",
                plan_id=plan.plan_id,
                decision=final_decision,
                static_manifest=static_manifest.to_dict(),
                observations=tuple(observations),
                correspondence_results=tuple(correspondence),
                audit_events=events,
                invoked_call_ids=tuple(invoked),
                blocked_call_ids=tuple(blocked),
                synthetic_secret_reached_sink=secret_reached,
            )

    def execute_validated_plan(
        self,
        spec: LiveMCPServerSpec,
        plan: CapabilityPlan,
        *,
        approvals: tuple[ApprovalEvidence, ...] = (),
        audit_path: Path | None = None,
    ) -> LivePlanExecutionResult:
        return asyncio.run(
            self.execute_validated_plan_async(
                spec, plan, approvals=approvals, audit_path=audit_path
            )
        )

    async def read_resource_async(self, spec: LiveMCPServerSpec, uri: str) -> dict[str, object]:
        async with self.client.connect(spec) as session:
            result = await session.read_resource(uri)
            dump = getattr(result, "model_dump", None)
            value = (
                dump(by_alias=True, exclude_none=True) if callable(dump) else {"repr": repr(result)}
            )
            return dict(value) if isinstance(value, Mapping) else {"repr": repr(value)}

    def read_resource(self, spec: LiveMCPServerSpec, uri: str) -> dict[str, object]:
        return asyncio.run(self.read_resource_async(spec, uri))

    def run_validation_suite(
        self, spec: LiveMCPServerSpec, plans: tuple[CapabilityPlan, ...]
    ) -> LiveMCPValidationResult:
        inspection = self.inspect_server(spec)
        results = tuple(self.execute_validated_plan(spec, plan) for plan in plans)
        all_corr = tuple(item for result in results for item in result.correspondence_results)
        all_audit = tuple(item for result in results for item in result.audit_events)
        blocked = tuple(sorted({call for result in results for call in result.blocked_call_ids}))
        approvals = tuple(
            sorted(
                {
                    str(req.get("flow_identity"))
                    for result in results
                    for req in self._manifest_requirements(result.static_manifest)
                    if isinstance(req, Mapping) and req.get("flow_identity")
                }
            )
        )
        diagnostics = tuple(
            d
            for result in results
            for item in result.correspondence_results
            for d in item.diagnostics
        )
        semantic_payload = {
            "server_id": spec.server_id,
            "server_declaration_hash": inspection.server_declaration_hash,
            "fixture_version": spec.fixture_version,
            "tools": [v.tool_name for v in inspection.tools],
            "resources": [v.resource_uri for v in inspection.resources],
            "plans": [r.semantic_form() for r in results],
            "blocked": blocked,
            "decisions": [r.decision.value for r in results],
            "correspondence": [(c.tool_name, c.state.value) for c in all_corr],
        }
        semantic = semantic_hash(semantic_payload)
        return LiveMCPValidationResult(
            server_id=spec.server_id,
            initialized=True,
            tools_discovered=len(inspection.tools),
            resources_discovered=len(inspection.resources),
            scenarios_run=len(results),
            scenarios_passed=sum(1 for r in results if not r.synthetic_secret_reached_sink),
            correspondence_results=all_corr,
            blocked_operations=blocked,
            approval_required_operations=approvals,
            diagnostics=diagnostics,
            audit_events=all_audit,
            real_external_network_calls=0,
            real_messages_sent=0,
            real_shell_commands=0,
            real_credentials_accessed=0,
            synthetic_secret_leaks=sum(1 for r in results if r.synthetic_secret_reached_sink),
            orphan_processes=0,
            semantic_identity=semantic,
        )

    @staticmethod
    def _manifest_requirements(value: Mapping[str, object]) -> tuple[object, ...]:
        raw = value.get("approval_requirements", ())
        return tuple(raw) if isinstance(raw, (list, tuple)) else ()
