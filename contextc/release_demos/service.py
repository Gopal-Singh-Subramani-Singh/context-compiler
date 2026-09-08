"""Typed M16 service for bounded, offline release demonstrations."""

from __future__ import annotations

import json
import tempfile
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import cast

from contextc.application.compile import (
    CompileRepositoryRequest,
    TargetCompilation,
    compile_prepared_target,
    compile_source_to_path,
    prepare_source_target,
)
from contextc.benchmark.fingerprint import equal_footing_fingerprint
from contextc.benchmark.metrics import calculate_raw_metrics
from contextc.benchmark.models import GroundTruth, SelectedLocation
from contextc.benchmark.source import SourceSpan, selected_span_from_source
from contextc.canonical import to_canonical_primitive
from contextc.capabilities.mcp_tools import load_declaration_directory
from contextc.capabilities.plan import load_plan
from contextc.capabilities.policy import load_policy as load_capability_policy
from contextc.capabilities.service import CapabilityService
from contextc.incremental.models import IncrementalCompileRequest
from contextc.incremental.service import IncrementalService
from contextc.optimization import OptimizerConfiguration
from contextc.release_demos.models import (
    DemoKind,
    DemoRunResult,
    DemoVerification,
    RegistryVerification,
    ReleaseDemo,
)
from contextc.release_demos.registry import (
    load_registry,
    resource_for,
    verify_file_record,
)
from contextc.reproduction import rebuild_build, verify_build
from contextc.targets import TargetId


def _mapping(value: object) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise AssertionError("expected canonical mapping")
    return cast(Mapping[str, object], value)


def _primitive_mapping(value: object) -> Mapping[str, object]:
    return _mapping(to_canonical_primitive(value))


def _diagnostic_codes(result: TargetCompilation) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                item.code.value
                for item in (
                    *result.index.diagnostics,
                    *result.supersession.diagnostics,
                    *result.conflicts.diagnostics,
                    *result.security.diagnostics,
                )
            }
        )
    )


def _compile_view(result: TargetCompilation) -> Mapping[str, object]:
    selected = set(result.rendered.ordered_node_ids)
    return {
        "target": result.rendered.target_id.value,
        "configured_budget": result.rendered.budget_evidence.configured_budget,
        "final_token_count": result.rendered.exact_token_count,
        "selected_node_ids": result.rendered.ordered_node_ids,
        "excluded_node_ids": tuple(
            node_id for node_id in result.graph.node_ids if node_id not in selected
        ),
        "optimizer_requested": result.selection.requested_strategy_id,
        "optimizer_used": result.selection.strategy_id,
        "optimizer_status": result.selection.optimizer_status.value,
        "optimizer_runtime_ms": result.selection.solver_runtime_ms,
        "diagnostic_codes": _diagnostic_codes(result),
    }


def _graph_view(result: TargetCompilation) -> Mapping[str, object]:
    selected = set(result.rendered.ordered_node_ids)
    return {
        "graph_identity": result.source_graph.semantic_identity,
        "nodes": tuple(
            {
                **node.to_dict(),
                "selected": node.node_id in selected,
            }
            for node in result.source_graph.nodes
        ),
        "edges": tuple(edge.to_dict() for edge in result.source_graph.edges),
    }


def _security_view(result: TargetCompilation) -> Mapping[str, object]:
    return {
        "policy_identity": result.security.policy_identity,
        "blocked": result.security.blocked,
        "node_facts": tuple(
            {
                "node_id": node.node_id,
                "source_uri": node.source.uri,
                "trust_domain": node.trust_domain.value,
                "sensitivity": node.sensitivity.value,
                "instruction_authority": node.instruction_authority.value,
            }
            for node in result.source_graph.nodes
        ),
        "diagnostics": tuple(item.to_dict() for item in result.security.diagnostics),
        "taint_paths": tuple(_primitive_mapping(item) for item in result.security.taint_paths),
        "transformations": result.security.transformations,
        "decisions": tuple(_primitive_mapping(item) for item in result.security.decisions),
    }


def _selected_locations(
    result: TargetCompilation, *, repository_id: str
) -> tuple[SelectedLocation, ...]:
    analyses = {item.node_id: item for item in result.analyses}
    tokenizer_id = result.rendered.tokenizer_identity.tokenizer_id
    values: list[SelectedLocation] = []
    for rank, node_id in enumerate(result.rendered.ordered_node_ids, start=1):
        node = result.graph.get_node(node_id)
        values.append(
            SelectedLocation(
                node_id=node_id,
                span=selected_span_from_source(
                    source_uri=node.source.uri,
                    start_line=node.source.start_line,
                    end_line=node.source.end_line,
                    repository_id=repository_id,
                ),
                source_tokens=analyses[node_id].token_counts[tokenizer_id],
                rank=rank,
            )
        )
    return tuple(values)


@contextmanager
def _materialized(demo: ReleaseDemo) -> Iterator[Path]:
    with tempfile.TemporaryDirectory(prefix=f"contextc-release-{demo.demo_id}-") as temporary:
        root = Path(temporary)
        files_root = resource_for(demo.demo_id, "files")

        def copy_tree(source: Traversable, destination: Path) -> None:
            for child in source.iterdir():
                target = destination / child.name
                if child.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    copy_tree(child, target)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(child.read_bytes())

        copy_tree(files_root, root)
        yield root


class DemoService:
    """Read-only application service for the four packaged M16 release demos."""

    def __init__(self) -> None:
        self._registry = load_registry()

    @property
    def registry_id(self) -> str:
        return self._registry.registry_id

    def list_demos(self) -> tuple[ReleaseDemo, ...]:
        return self._registry.demos

    def descriptor(self, demo_id: str) -> ReleaseDemo:
        match = next((item for item in self._registry.demos if item.demo_id == demo_id), None)
        if match is None:
            raise ValueError(f"unknown release demo {demo_id!r}")
        return match

    def verify_registry(self) -> RegistryVerification:
        problems: list[str] = []
        if (self._registry.schema_major, self._registry.schema_minor) != (1, 0):
            problems.append("unsupported release-demo registry schema")
        if len(self._registry.demos) != 4:
            problems.append("release registry must contain exactly four demos")
        expected_kinds = set(DemoKind)
        actual_kinds = {item.kind for item in self._registry.demos}
        if actual_kinds != expected_kinds:
            problems.append("release registry does not contain the four required demo kinds")
        demo_results = tuple(self._verify_integrity(item) for item in self._registry.demos)
        return RegistryVerification(
            valid=not problems and all(item.valid for item in demo_results),
            registry_id=self._registry.registry_id,
            demos_checked=len(demo_results),
            demo_results=demo_results,
            problems=tuple(problems),
        )

    def verify_demo(self, demo_id: str) -> DemoVerification:
        demo = self.descriptor(demo_id)
        integrity = self._verify_integrity(demo)
        problems = list(integrity.problems)
        checks = list(integrity.semantic_checks)
        if not problems:
            try:
                result = self.run_demo(demo_id)
                semantic = self._semantic_checks(demo, result)
                checks.extend(semantic)
            except Exception as error:
                problems.append(f"semantic verification failed: {type(error).__name__}: {error}")
        return DemoVerification(
            demo_id=demo_id,
            valid=not problems,
            files_checked=integrity.files_checked,
            semantic_checks=tuple(checks),
            problems=tuple(problems),
        )

    def verify_all(self) -> RegistryVerification:
        registry_check = self.verify_registry()
        problems = list(registry_check.problems)
        results = tuple(self.verify_demo(item.demo_id) for item in self._registry.demos)
        return RegistryVerification(
            valid=not problems and all(item.valid for item in results),
            registry_id=self._registry.registry_id,
            demos_checked=len(results),
            demo_results=results,
            problems=tuple(problems),
        )

    def run_demo(
        self,
        demo_id: str,
        *,
        strategy: str | None = None,
        budget: int | None = None,
        target: str | None = None,
    ) -> DemoRunResult:
        demo = self.descriptor(demo_id)
        if demo.kind is DemoKind.REPOSITORY_BUG:
            return self._run_repository_bug(demo, strategy, budget, target)
        if demo.kind is DemoKind.INCIDENT_RESPONSE:
            return self._run_incident(demo, strategy, budget, target)
        if demo.kind is DemoKind.INCREMENTAL_REBUILD:
            return self._run_incremental(demo, strategy, budget, target)
        if any(value is not None for value in (strategy, budget, target)):
            raise ValueError("capability-composition uses a fixed static release profile")
        return self._run_capability(demo)

    @staticmethod
    def _required_int(value: object, field: str) -> int:
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{field} must be an integer")
        return value

    @staticmethod
    def _target(value: str) -> TargetId:
        if value not in {TargetId.GENERIC.value, TargetId.STRUCTURED_JSON.value}:
            raise ValueError("release demo target must be generic or structured-json")
        return TargetId(value)

    def _verify_integrity(self, demo: ReleaseDemo) -> DemoVerification:
        problems: list[str] = []
        if not demo.offline:
            problems.append("release demo is not declared offline")
        if demo.tool_execution:
            problems.append("release demo declares tool execution")
        for record in demo.files:
            problems.extend(verify_file_record(demo.demo_id, record))
        return DemoVerification(
            demo_id=demo.demo_id,
            valid=not problems,
            files_checked=len(demo.files),
            semantic_checks=("registry_schema", "resource_integrity", "offline_no_execution"),
            problems=tuple(problems),
        )

    def _semantic_checks(self, demo: ReleaseDemo, result: DemoRunResult) -> tuple[str, ...]:
        checks: list[str] = []
        if demo.kind is DemoKind.REPOSITORY_BUG:
            required = str(demo.expected["required_source"])
            selected_sources = result.summary.get("selected_source_uris")
            if not isinstance(selected_sources, tuple) or required not in selected_sources:
                raise ValueError("repository demo did not select the required source")
            checks.extend(("required_release_source_selected", "m4_reproduction"))
        elif demo.kind is DemoKind.INCIDENT_RESPONSE:
            expected_codes = demo.expected.get("diagnostic_codes")
            codes = result.compile.get("diagnostic_codes")
            if not isinstance(expected_codes, list) or not isinstance(codes, tuple):
                raise ValueError("incident diagnostic evidence is malformed")
            missing = sorted(set(str(item) for item in expected_codes) - set(codes))
            if missing:
                raise ValueError(f"incident demo missing diagnostics {missing}")
            expected_suffix = str(demo.expected["superseded_source_suffix"])
            superseded_sources = result.summary.get("superseded_source_uris")
            if not isinstance(superseded_sources, tuple) or not any(
                str(item).endswith(expected_suffix) for item in superseded_sources
            ):
                raise ValueError("incident demo did not preserve expected supersession evidence")
            checks.extend(("incident_diagnostics", "supersession", "security"))
        elif demo.kind is DemoKind.INCREMENTAL_REBUILD:
            equivalent = result.incremental_capabilities.get("equivalent_to_clean")
            if equivalent is not True:
                raise ValueError("incremental demo is not equivalent to a clean build")
            checks.extend(("incremental_equivalence", "selective_recompute"))
        else:
            execution = result.incremental_capabilities.get("tool_execution_performed")
            risks = result.incremental_capabilities.get("risk_kinds")
            if execution is not False or not isinstance(risks, tuple):
                raise ValueError("capability demo evidence is malformed")
            if str(demo.expected["risk_kind"]) not in risks:
                raise ValueError("capability demo did not detect expected risk")
            decisions = result.incremental_capabilities.get("decisions")
            if not isinstance(decisions, tuple) or not any(
                isinstance(item, Mapping) and item.get("action") == demo.expected["decision"]
                for item in decisions
            ):
                raise ValueError("capability demo did not preserve expected policy decision")
            checks.extend(("static_capability_flow", "approval_requirement", "no_execution"))
        return tuple(checks)

    def _run_repository_bug(
        self,
        demo: ReleaseDemo,
        strategy: str | None,
        budget: int | None,
        target: str | None,
    ) -> DemoRunResult:
        with _materialized(demo) as root:
            task = _mapping(json.loads((root / "task.json").read_text(encoding="utf-8")))
            repository = root / "repo"
            anchor = datetime.fromisoformat(str(task["time_anchor"]).replace("Z", "+00:00"))
            base = CompileRepositoryRequest(
                repository=repository,
                task=str(task["description"]),
                target_id=self._target(target or demo.default_target),
                token_budget=demo.default_budget if budget is None else budget,
                time_anchor=anchor,
                source_revision=str(task["pre_fix_revision"]),
                system_instruction="Use only the supplied reduced pre-fix repository evidence.",
                optimizer=OptimizerConfiguration(
                    requested_strategy=demo.default_strategy if strategy is None else strategy,
                    source_content_allowance=self._required_int(
                        task["source_content_allowance"], "source_content_allowance"
                    ),
                ),
            )
            artifact = root / "build" / "repository-bug.txt"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            result = compile_source_to_path(base, artifact)
            manifest = artifact.with_name(artifact.name + ".manifest.json")
            verified = verify_build(manifest, source_root=repository)
            rebuilt_path = root / "build" / "repository-bug.rebuilt.txt"
            rebuilt = rebuild_build(manifest, output_path=rebuilt_path, source_root=repository)
            comparison = self._repository_comparison(base, task)
            selected_sources = tuple(
                result.graph.get_node(node_id).source.uri
                for node_id in result.rendered.ordered_node_ids
            )
            return DemoRunResult(
                demo_id=demo.demo_id,
                kind=demo.kind,
                title=demo.title,
                summary={
                    "bounded_claim": demo.description,
                    "historical_source_revision": task["pre_fix_revision"],
                    "historical_fix_revision": task["historical_fix_revision"],
                    "selected_source_uris": selected_sources,
                    "full_m11_case_study_separate": True,
                },
                compile=_compile_view(result),
                graph=_graph_view(result),
                comparison=comparison,
                reproduction={
                    "verification_status": verified.status,
                    "artifact_identity": verified.artifact_identity,
                    "rebuilt_artifact_identity": rebuilt.artifact_identity,
                    "byte_identical": artifact.read_bytes() == rebuilt_path.read_bytes(),
                },
                security=_security_view(result),
                incremental_capabilities={"not_applicable": True},
            )

    def _repository_comparison(
        self, base: CompileRepositoryRequest, task: Mapping[str, object]
    ) -> Mapping[str, object]:
        prepared = prepare_source_target(base)
        required = SourceSpan(
            "repo://python-humanize/src/humanize/lists.py",
            self._required_int(task["required_start_line"], "required_start_line"),
            self._required_int(task["required_end_line"], "required_end_line"),
        )
        labels = GroundTruth(required_spans=(required,))
        rows: list[Mapping[str, object]] = []
        fingerprints: set[str] = set()
        for strategy in ("naive", "graph_closure_greedy", "auto"):
            request = replace(
                base,
                optimizer=replace(base.optimizer, requested_strategy=strategy),
            )
            started = time.perf_counter()
            result = compile_prepared_target(request, prepared)
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            fingerprint = equal_footing_fingerprint(request, result)
            fingerprints.add(fingerprint)
            selected = _selected_locations(result, repository_id="python-humanize")
            metrics = calculate_raw_metrics(
                labels=labels,
                selected=selected,
                final_rendered_tokens=result.rendered.exact_token_count,
                configured_budget=result.rendered.budget_evidence.configured_budget,
                compilation_latency_ms=elapsed_ms,
                optimizer_runtime_ms=result.selection.solver_runtime_ms,
            )
            rows.append(
                {
                    "requested_strategy": strategy,
                    "optimizer_used": result.selection.strategy_id,
                    "optimizer_status": result.selection.optimizer_status.value,
                    "runtime_ms": elapsed_ms,
                    "selected_node_ids": result.rendered.ordered_node_ids,
                    "final_token_count": result.rendered.exact_token_count,
                    "raw_m6_metrics": _primitive_mapping(metrics),
                    "input_fingerprint": fingerprint,
                }
            )
        if len(fingerprints) != 1:
            raise ValueError("release demo comparison is not equal-footing")
        return {
            "equal_footing_fingerprint": next(iter(fingerprints)),
            "rows": tuple(rows),
            "claim": "Raw metrics are reported without claiming a universal winning strategy.",
        }

    def _run_incident(
        self,
        demo: ReleaseDemo,
        strategy: str | None,
        budget: int | None,
        target: str | None,
    ) -> DemoRunResult:
        with _materialized(demo) as root:
            public = root / "public"
            raw = _mapping(json.loads((public / "incident.json").read_text(encoding="utf-8")))
            anchor = datetime.fromisoformat(str(raw["time_anchor"]))
            request = CompileRepositoryRequest(
                repository=public,
                task=str(raw["task"]),
                target_id=self._target(target or demo.default_target),
                token_budget=demo.default_budget if budget is None else budget,
                time_anchor=anchor,
                source_adapter_id="incident",
                optimizer=OptimizerConfiguration(
                    requested_strategy=demo.default_strategy if strategy is None else strategy
                ),
            )
            artifact = root / "build" / "incident.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            result = compile_source_to_path(request, artifact)
            manifest = artifact.with_name(artifact.name + ".manifest.json")
            verified = verify_build(manifest, source_root=public)
            rebuilt_path = root / "build" / "incident.rebuilt.json"
            rebuilt = rebuild_build(manifest, output_path=rebuilt_path, source_root=public)
            superseded_sources = tuple(
                result.source_graph.get_node(node_id).source.uri
                for node_id in result.supersession.superseded_node_ids
            )
            return DemoRunResult(
                demo_id=demo.demo_id,
                kind=demo.kind,
                title=demo.title,
                summary={
                    "bounded_claim": demo.description,
                    "incident_id": raw["incident_id"],
                    "superseded_node_ids": result.supersession.superseded_node_ids,
                    "superseded_source_uris": superseded_sources,
                },
                compile=_compile_view(result),
                graph=_graph_view(result),
                comparison={"not_applicable": True},
                reproduction={
                    "verification_status": verified.status,
                    "artifact_identity": verified.artifact_identity,
                    "rebuilt_artifact_identity": rebuilt.artifact_identity,
                    "byte_identical": artifact.read_bytes() == rebuilt_path.read_bytes(),
                },
                security=_security_view(result),
                incremental_capabilities={"not_applicable": True},
            )

    def _run_incremental(
        self,
        demo: ReleaseDemo,
        strategy: str | None,
        budget: int | None,
        target: str | None,
    ) -> DemoRunResult:
        with _materialized(demo) as root:
            repository = root / "repo"
            change = _mapping(json.loads((root / "change.json").read_text(encoding="utf-8")))
            anchor = datetime.fromisoformat(str(change["time_anchor"]).replace("Z", "+00:00"))
            request = CompileRepositoryRequest(
                repository=repository,
                task=str(change["task"]),
                target_id=self._target(target or demo.default_target),
                token_budget=demo.default_budget if budget is None else budget,
                time_anchor=anchor,
                optimizer=OptimizerConfiguration(
                    requested_strategy=demo.default_strategy if strategy is None else strategy
                ),
            )
            cache_root = root / "cache"
            service = IncrementalService()
            first = service.build(
                IncrementalCompileRequest(
                    compile_request=request,
                    output_path=root / "build" / "first.txt",
                    cache_root=cache_root,
                    verify_against_clean=True,
                )
            )
            source = repository / str(change["path"])
            before = str(change["before"])
            after = str(change["after"])
            content = source.read_text(encoding="utf-8")
            if before not in content:
                raise ValueError("incremental release demo source does not contain expected text")
            source.write_text(content.replace(before, after, 1), encoding="utf-8")
            second = service.build(
                IncrementalCompileRequest(
                    compile_request=request,
                    output_path=root / "build" / "second.txt",
                    cache_root=cache_root,
                    verify_against_clean=True,
                )
            )
            equivalent = second.equivalence is not None and second.equivalence.equivalent
            return DemoRunResult(
                demo_id=demo.demo_id,
                kind=demo.kind,
                title=demo.title,
                summary={
                    "bounded_claim": demo.description,
                    "changed_source_uri": demo.expected["changed_source_uri"],
                },
                compile=_compile_view(second.compilation),
                graph=_graph_view(second.compilation),
                comparison={"not_applicable": True},
                reproduction={
                    "incremental_full_equivalent": equivalent,
                    "differences": (
                        () if second.equivalence is None else second.equivalence.differences
                    ),
                },
                security=_security_view(second.compilation),
                incremental_capabilities={
                    "cold_cache_report": first.cache_report.to_dict(),
                    "changed_cache_report": second.cache_report.to_dict(),
                    "equivalent_to_clean": equivalent,
                    "changed_source_uri": demo.expected["changed_source_uri"],
                    "tool_execution_performed": False,
                },
            )

    def _run_capability(self, demo: ReleaseDemo) -> DemoRunResult:
        with _materialized(demo) as root:
            tools, resources = load_declaration_directory(root / "declarations")
            plan = load_plan(root / "plan.json")
            policy = load_capability_policy()
            service = CapabilityService()
            manifest = service.analyze_plan(plan, tools, resources, policy)
            graph = service.build_graph(plan, tools, resources)
            risks = tuple(sorted({item.risk_kind.value for item in manifest.flows}))
            decisions = tuple(
                {
                    "flow_identity": item.flow_identity,
                    "rule_id": item.rule_id,
                    "action": item.action.value,
                    "approval_identity": item.approval_identity,
                }
                for item in manifest.decisions
            )
            return DemoRunResult(
                demo_id=demo.demo_id,
                kind=demo.kind,
                title=demo.title,
                summary={
                    "bounded_claim": demo.description,
                    "analysis_mode": manifest.analysis_mode,
                    "tool_execution_performed": manifest.tool_execution_performed,
                },
                compile={
                    "analysis_mode": manifest.analysis_mode,
                    "tool_execution_performed": manifest.tool_execution_performed,
                    "plan_id": manifest.plan_id,
                    "diagnostic_codes": tuple(item.code.value for item in manifest.diagnostics),
                    "blocked": manifest.blocked,
                    "pending_approval": manifest.pending_approval,
                    "allowed": manifest.allowed,
                },
                graph={
                    "graph_identity": graph.identity,
                    "nodes": tuple(_primitive_mapping(item) for item in graph.nodes),
                    "edges": tuple(_primitive_mapping(item) for item in graph.edges),
                },
                comparison={"not_applicable": True},
                reproduction={
                    "plan_identity": manifest.plan_identity,
                    "policy_identity": manifest.policy_identity,
                    "declaration_identities": {
                        "tools": manifest.tool_declaration_identities,
                        "resources": manifest.resource_declaration_identities,
                    },
                },
                security={
                    "risk_kinds": risks,
                    "decisions": decisions,
                    "approval_requirements": tuple(
                        _primitive_mapping(item) for item in manifest.approval_requirements
                    ),
                },
                incremental_capabilities={
                    "analysis_mode": manifest.analysis_mode,
                    "tool_execution_performed": manifest.tool_execution_performed,
                    "risk_kinds": risks,
                    "decisions": decisions,
                    "approval_requirements": tuple(
                        _primitive_mapping(item) for item in manifest.approval_requirements
                    ),
                },
            )
