"""Verified M8 incremental pipeline using content-addressed intermediate stages."""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from contextc.application.compile import (
    AnalysisResolver,
    CompileRepositoryRequest,
    SecurityResolver,
    SupersessionResolver,
    TargetCompilation,
    analyze_node_for_task,
    compile_prepared_target,
    compile_source_to_path,
    prepare_adapted_target,
)
from contextc.cache.dependency_index import DependencyIndex
from contextc.cache.equivalence import (
    EquivalenceResult,
    combine_equivalence,
    compare_compilations,
    compare_manifests,
)
from contextc.cache.keys import ComputationKey
from contextc.cache.reports import CacheReport, CacheStageEvent
from contextc.cache.source_index import SourceIndex
from contextc.cache.stagekeys import stage_key
from contextc.cache.store import ContentAddressedStore
from contextc.cache.wrappers import (
    decode_adapted_context,
    decode_security_result,
    decode_supersession_result,
    encode_adapted_context,
    encode_security_result,
    encode_supersession_result,
)
from contextc.canonical import canonical_json_bytes
from contextc.cross_domain.adapters import AdaptedContext, RepositoryAdapter, load_source_context
from contextc.cross_domain.supersession import SupersessionPolicy, SupersessionResult
from contextc.diagnostics import DiagnosticCode
from contextc.hashing import digest_bytes, semantic_hash
from contextc.incremental.models import IncrementalCompileRequest, IncrementalCompileResult
from contextc.ir import ContextGraph, Sensitivity
from contextc.ir.analysis import NodeAnalysis
from contextc.reproduction import read_build_manifest
from contextc.reproduction.service import write_compilation_transaction
from contextc.security import (
    ANALYSIS_VERSION as SECURITY_ANALYSIS_VERSION,
)
from contextc.security import (
    SecurityPolicy,
    SecurityResult,
    SecurityService,
)
from contextc.security import (
    policy_identity as security_policy_identity,
)
from contextc.source_rules import source_rules_identity
from contextc.targets import TargetId
from contextc.tokenizers import TargetTokenizer

_SKIP_PARTS = frozenset({".git", ".contextc", "__pycache__", ".pytest_cache"})


def _adapter_version(adapter_id: str) -> str:
    if adapter_id == "repository":
        return RepositoryAdapter.adapter_version
    if adapter_id == "incident":
        from contextc.cross_domain.incident import IncidentAdapter

        return IncidentAdapter.adapter_version
    raise ValueError(f"unknown source adapter {adapter_id!r}")


def _discover_source_files(root: Path, adapter_id: str) -> tuple[Path, ...]:
    root = root.resolve()
    if adapter_id == "repository":
        # Mirror RepositoryParser's default hidden-file semantics exactly enough
        # to conservatively invalidate on every visible file change.
        result = []
        for path in root.rglob("*"):
            rel = path.relative_to(root)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if any(part in _SKIP_PARTS for part in rel.parts):
                continue
            if path.is_file() or path.is_symlink():
                result.append(path)
        return tuple(sorted(result, key=lambda p: p.relative_to(root).as_posix()))
    if adapter_id == "incident":
        manifest = root / "incident.json"
        if not manifest.exists():
            return ()
        raw = json.loads(manifest.read_text(encoding="utf-8"))
        paths = {manifest}
        if isinstance(raw, dict):
            sources = raw.get("sources", [])
            if isinstance(sources, list):
                for item in sources:
                    if isinstance(item, dict) and isinstance(item.get("path"), str):
                        paths.add(root / "sources" / item["path"])
        return tuple(sorted(paths, key=lambda p: p.relative_to(root).as_posix()))
    raise ValueError(f"unknown source adapter {adapter_id!r}")


def _source_snapshot(root: Path, adapter_id: str) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    root = root.resolve()
    for path in _discover_source_files(root, adapter_id):
        rel = path.relative_to(root).as_posix()
        if path.is_symlink():
            identity = semantic_hash({"symlink": rel})
        else:
            try:
                identity = digest_bytes(path.read_bytes())
            except OSError as error:
                identity = semantic_hash({"unreadable": rel, "error_type": type(error).__name__})
        values.append((rel, identity))
    return tuple(values)


def _source_uri_for_path(root: Path, adapter_id: str, relative_path: str) -> str:
    if adapter_id == "repository":
        return f"repo:///{relative_path}"
    if adapter_id == "incident":
        try:
            raw = json.loads((root / "incident.json").read_text(encoding="utf-8"))
            incident_id = raw.get("incident_id", "unknown") if isinstance(raw, dict) else "unknown"
        except (OSError, json.JSONDecodeError):
            incident_id = "unknown"
        if relative_path == "incident.json":
            return f"incident://{incident_id}/incident.json"
        cleaned = relative_path.removeprefix("sources/")
        return f"incident://{incident_id}/{cleaned}"
    return f"file:///{relative_path}"


class IncrementalPipeline:
    def __init__(self, cache_root: Path) -> None:
        self.cache_root = cache_root
        self.store = ContentAddressedStore(cache_root)
        self.dependencies = DependencyIndex(cache_root / "dependency-index.json")
        self.sources = SourceIndex(cache_root / "source-index" / "sources.json")
        self._events: list[CacheStageEvent] = []

    def _event(
        self, stage: str, key_identity: str, status: str, source_uri: str | None = None
    ) -> None:
        self._events.append(CacheStageEvent(stage, key_identity, status, source_uri))

    def _record(
        self,
        key: ComputationKey,
        payload: bytes,
        *,
        dependencies: tuple[str, ...] = (),
        source_uris: tuple[str, ...] = (),
    ) -> None:
        self.store.put(key, payload, dependencies=dependencies, source_uris=source_uris)
        self.dependencies.record(key.identity, dependencies)
        for source_uri in source_uris:
            self.sources.record(source_uri, key.identity)

    def _load_adapted(
        self, request: CompileRepositoryRequest
    ) -> tuple[AdaptedContext, str, tuple[str, ...]]:
        root = request.repository.resolve()
        snapshot = _source_snapshot(root, request.source_adapter_id)
        source_key_ids: list[str] = []
        for relative_path, content_identity in snapshot:
            uri = _source_uri_for_path(root, request.source_adapter_id, relative_path)
            key = stage_key(
                "source_content",
                {"source_uri": uri, "content_identity": content_identity},
            )
            source_key_ids.append(key.identity)
            existing = self.store.get(key)
            if existing is None:
                self._record(
                    key,
                    canonical_json_bytes({"source_uri": uri, "content_identity": content_identity}),
                    source_uris=(uri,),
                )
                self._event("source_content", key.identity, "recomputed", uri)
            else:
                self._event("source_content", key.identity, "reused", uri)

        parse_key = stage_key(
            "parse",
            {
                "adapter_id": request.source_adapter_id,
                "adapter_version": _adapter_version(request.source_adapter_id),
                "source_revision": request.source_revision,
                "source_rules_identity": source_rules_identity(request.source_rules),
                "snapshot": snapshot,
            },
        )
        entry = self.store.get(parse_key)
        if entry is not None:
            try:
                index, graph, adapter_id, adapter_version = decode_adapted_context(entry.payload)
                adapted = AdaptedContext(adapter_id, adapter_version, index, graph)
                self._event("parse", parse_key.identity, "reused")
                return adapted, parse_key.identity, tuple(source_key_ids)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                entry = None

        adapted = load_source_context(
            request.source_adapter_id,
            request.repository,
            revision=request.source_revision,
            source_rules=request.source_rules,
        )
        # Do not persist raw source graphs that contain secret source facts. The
        # source-content fingerprints above remain safe to cache.
        if not any(node.sensitivity is Sensitivity.SECRET for node in adapted.graph.nodes):
            self._record(
                parse_key,
                encode_adapted_context(
                    adapted.index,
                    adapted.graph,
                    adapter_id=adapted.adapter_id,
                    adapter_version=adapted.adapter_version,
                ),
                dependencies=tuple(source_key_ids),
                source_uris=tuple(sorted({node.source.uri for node in adapted.graph.nodes})),
            )
        else:
            self.dependencies.record(parse_key.identity, tuple(source_key_ids))
            for uri in sorted({node.source.uri for node in adapted.graph.nodes}):
                self.sources.record(uri, parse_key.identity)
        self._event("parse", parse_key.identity, "recomputed")
        return adapted, parse_key.identity, tuple(source_key_ids)

    def _security_resolver(self, parse_key_identity: str) -> SecurityResolver:
        def resolve(graph: ContextGraph, policy: SecurityPolicy) -> SecurityResult:
            key = stage_key(
                "security",
                {
                    "source_graph_identity": graph.semantic_identity,
                    "policy_identity": security_policy_identity(policy),
                    "analysis_version": SECURITY_ANALYSIS_VERSION,
                },
            )
            entry = self.store.get(key)
            if entry is not None:
                try:
                    result = decode_security_result(entry.payload)
                    self._event("security", key.identity, "reused")
                    return result
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    pass
            result = SecurityService(policy).scan_graph(graph)
            # SecurityResult contains only transformed/redacted visible nodes.
            self._record(
                key,
                encode_security_result(result),
                dependencies=(parse_key_identity,),
                source_uris=tuple(sorted({node.source.uri for node in graph.nodes})),
            )
            self._event("security", key.identity, "recomputed")
            return result

        return resolve

    def _supersession_resolver(self, parse_key_identity: str) -> SupersessionResolver:
        def resolve(graph: ContextGraph, policy: SupersessionPolicy) -> SupersessionResult:
            from contextc.cross_domain.supersession import analyze_supersession

            key = stage_key(
                "supersession",
                {
                    "source_graph_identity": graph.semantic_identity,
                    "policy_identity": policy.identity,
                },
            )
            entry = self.store.get(key)
            if entry is not None:
                try:
                    result = decode_supersession_result(entry.payload)
                    self._event("supersession", key.identity, "reused")
                    return result
                except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                    pass
            result = analyze_supersession(graph, policy)
            self._record(
                key,
                encode_supersession_result(result),
                dependencies=(parse_key_identity,),
                source_uris=tuple(sorted({node.source.uri for node in graph.nodes})),
            )
            self._event("supersession", key.identity, "recomputed")
            return result

        return resolve

    def _analysis_resolver(
        self,
        request: CompileRepositoryRequest,
        security_key_identity: str | None = None,
    ) -> AnalysisResolver:
        def resolve(
            graph: ContextGraph,
            task: str,
            tokenizer: TargetTokenizer,
            target_id: TargetId,
            time_anchor: datetime,
        ) -> tuple[NodeAnalysis, ...]:
            analyses: list[NodeAnalysis] = []
            for node in graph.nodes:
                token_key = stage_key(
                    "token_count",
                    {
                        "node": node.to_dict(),
                        "target_id": target_id.value,
                        "tokenizer": tokenizer.identity,
                    },
                )
                token_entry = self.store.get(token_key)
                if token_entry is not None:
                    try:
                        raw = json.loads(token_entry.payload.decode("utf-8"))
                        token_count = int(raw["token_count"])
                        self._event("token_count", token_key.identity, "reused", node.source.uri)
                    except (
                        ValueError,
                        KeyError,
                        TypeError,
                        json.JSONDecodeError,
                        UnicodeDecodeError,
                    ):
                        token_entry = None
                if token_entry is None:
                    # Compute through the canonical analysis helper once, then split
                    # the target token count into its task-neutral cache stage.
                    fresh = analyze_node_for_task(
                        node,
                        task=task,
                        tokenizer=tokenizer,
                        target_id=target_id,
                        time_anchor=time_anchor,
                    )
                    token_count = fresh.token_counts[tokenizer.identity.tokenizer_id]
                    self._record(
                        token_key,
                        canonical_json_bytes({"token_count": token_count}),
                        dependencies=(
                            () if security_key_identity is None else (security_key_identity,)
                        ),
                        source_uris=(node.source.uri,),
                    )
                    self._event("token_count", token_key.identity, "recomputed", node.source.uri)

                analysis_key = stage_key(
                    "analysis",
                    {
                        "node": node.to_dict(),
                        "task": task,
                        "time_anchor": time_anchor,
                        "target_id": target_id.value,
                        "tokenizer_id": tokenizer.identity.tokenizer_id,
                        "token_count": token_count,
                    },
                )
                analysis_entry = self.store.get(analysis_key)
                if analysis_entry is not None:
                    try:
                        raw_analysis = json.loads(analysis_entry.payload.decode("utf-8"))
                        if not isinstance(raw_analysis, dict):
                            raise ValueError("analysis cache payload malformed")
                        analysis = NodeAnalysis.from_dict(raw_analysis)
                        self._event("analysis", analysis_key.identity, "reused", node.source.uri)
                        analyses.append(analysis)
                        continue
                    except (
                        ValueError,
                        KeyError,
                        TypeError,
                        json.JSONDecodeError,
                        UnicodeDecodeError,
                    ):
                        pass
                analysis = analyze_node_for_task(
                    node,
                    task=task,
                    tokenizer=tokenizer,
                    target_id=target_id,
                    time_anchor=time_anchor,
                    token_count=token_count,
                )
                self._record(
                    analysis_key,
                    canonical_json_bytes(analysis.to_dict()),
                    dependencies=(token_key.identity,),
                    source_uris=(node.source.uri,),
                )
                self._event("analysis", analysis_key.identity, "recomputed", node.source.uri)
                analyses.append(analysis)
            return tuple(analyses)

        return resolve

    def _record_downstream(
        self, request: CompileRepositoryRequest, result: TargetCompilation
    ) -> None:
        analysis_keys = tuple(
            event.key_identity for event in self._events if event.stage == "analysis"
        )
        selection_key = stage_key(
            "selection",
            {
                "source_graph": result.graph.semantic_identity,
                "analyses": [analysis.to_dict() for analysis in result.analyses],
                "optimizer": request.optimizer,
                "budget": request.token_budget,
                "security_exclusions": result.security.excluded_node_ids,
                "superseded": result.supersession.superseded_node_ids,
            },
        )
        self._record(
            selection_key,
            canonical_json_bytes(result.selection.to_dict()),
            dependencies=analysis_keys,
            source_uris=tuple(sorted({node.source.uri for node in result.graph.nodes})),
        )
        self._event("selection", selection_key.identity, "recomputed")
        lowering_key = stage_key(
            "lowering",
            {
                "selection": result.selection.to_dict(),
                "target_id": request.target_id.value,
                "tokenizer": result.rendered.tokenizer_identity,
                "instructions": {
                    "system": request.system_instruction,
                    "developer": request.developer_instruction,
                    "policy": request.policy_instruction,
                    "tool_schema": request.tool_schema_text,
                    "task": request.task,
                },
            },
        )
        self._record(
            lowering_key,
            result.rendered.rendered_bytes,
            dependencies=(selection_key.identity,),
        )
        self._event("lowering", lowering_key.identity, "recomputed")

    def compile(self, request: IncrementalCompileRequest) -> IncrementalCompileResult:
        self._events = []
        compile_request = request.compile_request
        adapted, parse_key_identity, _ = self._load_adapted(compile_request)
        security_key_holder: dict[str, str] = {}

        base_security_resolver = self._security_resolver(parse_key_identity)

        def security_resolver(graph: ContextGraph, policy: SecurityPolicy) -> SecurityResult:
            result = base_security_resolver(graph, policy)
            candidates = [e.key_identity for e in self._events if e.stage == "security"]
            if candidates:
                security_key_holder["key"] = candidates[-1]
            return result

        prepared = prepare_adapted_target(
            compile_request,
            adapted.index,
            adapted.graph,
            analysis_resolver=self._analysis_resolver(
                compile_request, security_key_holder.get("key")
            ),
            security_resolver=security_resolver,
            supersession_resolver=self._supersession_resolver(parse_key_identity),
        )
        # The security key is only known after the resolver ran; analysis cache keys
        # already include transformed node semantics, so correctness does not depend
        # on this operational dependency edge.
        result = compile_prepared_target(compile_request, prepared)
        self._record_downstream(compile_request, result)
        manifest_path = (
            request.manifest_path
            if request.manifest_path is not None
            else request.output_path.with_name(request.output_path.name + ".manifest.json")
        )
        write_compilation_transaction(
            request=compile_request,
            result=result,
            artifact_path=request.output_path,
            manifest_path=manifest_path,
        )

        equivalence: EquivalenceResult | None = None
        if request.verify_against_clean:
            with tempfile.TemporaryDirectory(prefix="contextc-m8-clean-") as temporary:
                clean_output = Path(temporary) / request.output_path.name
                clean = compile_source_to_path(compile_request, clean_output)
                clean_manifest_path = clean_output.with_name(clean_output.name + ".manifest.json")
                incremental_manifest = read_build_manifest(manifest_path)
                clean_manifest = read_build_manifest(clean_manifest_path)
                equivalence = combine_equivalence(
                    compare_compilations(result, clean),
                    compare_manifests(incremental_manifest, clean_manifest),
                )
            if not equivalence.equivalent:
                raise RuntimeError(
                    f"{DiagnosticCode.INCREMENTAL_FULL_MISMATCH.value} incremental/full mismatch: "
                    + "; ".join(equivalence.differences)
                )

        return IncrementalCompileResult(
            compilation=result,
            cache_report=CacheReport(tuple(self._events)),
            equivalence=equivalence,
            output_path=request.output_path,
            manifest_path=manifest_path,
        )
