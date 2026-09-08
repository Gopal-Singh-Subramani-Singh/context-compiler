"""Dependency-light command-line entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from contextc.canonical import to_canonical_primitive
from contextc.config import ProjectConfig, apply_cli_overrides, load_project_config
from contextc.errors import ContextCompilerError, SecurityPolicyBlockedError
from contextc.optional import OPTIONAL_MODULES, optional_dependency_available
from contextc.parsers import IndexPolicy, RepositoryParser
from contextc.version import __version__


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    ok: bool
    detail: str


def _writable_check(name: str, path: Path) -> DoctorCheck:
    try:
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix=".contextc-doctor-", dir=path):
            pass
    except OSError as error:
        return DoctorCheck(name, False, f"{path}: {error}")
    return DoctorCheck(name, True, str(path))


def doctor_report(
    *, base_path: Path, config_path: Path | None = None
) -> tuple[ProjectConfig, tuple[DoctorCheck, ...]]:
    """Run only the environment checks owned by M1."""

    config = load_project_config(config_path)
    checks = [
        DoctorCheck(
            "python",
            sys.version_info >= (3, 11),
            f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        ),
        DoctorCheck("configuration", True, config.identity),
        _writable_check("build_root", base_path / config.build_root),
        _writable_check("cache_root", base_path / config.cache_root),
    ]
    for feature, (module, _extra) in sorted(OPTIONAL_MODULES.items()):
        available = optional_dependency_available(module)
        checks.append(
            DoctorCheck(
                f"optional:{feature}",
                True,
                "available" if available else "not installed (optional)",
            )
        )
    return config, tuple(checks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="contextc",
        description="Compile typed, provenance-aware context with exact target budgets.",
    )
    parser.add_argument("--version", action="version", version=f"contextc {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("version", help="show the installed version")

    doctor = subparsers.add_parser("doctor", help="check the M1 local environment")
    doctor.add_argument("--config", type=Path, help="path to contextc.toml or pyproject.toml")
    doctor.add_argument("--json", action="store_true", help="emit structured JSON")

    index = subparsers.add_parser("index", help="statically index a repository")
    index.add_argument("path", type=Path)
    index.add_argument("--max-file-bytes", type=int)
    index.add_argument("--include-hidden", action="store_true", default=None)
    index.add_argument("--json", action="store_true", help="emit the complete index as JSON")

    compile_command = subparsers.add_parser(
        "compile", help="compile an exact-budget Generic, structured JSON, Qwen, or Llama target"
    )
    compile_command.add_argument("path", type=Path)
    compile_command.add_argument("--task", required=True)
    compile_command.add_argument(
        "--target", choices=("generic", "structured-json", "qwen", "llama"), default="generic"
    )
    compile_command.add_argument("--token-budget", type=int, required=True)
    compile_command.add_argument(
        "--optimizer",
        choices=(
            "auto",
            "naive",
            "recency",
            "top_k",
            "relevance_greedy",
            "density_greedy",
            "brute_force",
            "dynamic_programming",
            "ilp",
            "graph_closure_greedy",
        ),
        default="auto",
        help="M5 selection strategy (default: deterministic auto cascade)",
    )
    compile_command.add_argument("--source-content-allowance", type=int)
    compile_command.add_argument("--mandatory-node", action="append", default=[])
    compile_command.add_argument("--block-node", action="append", default=[])
    compile_command.add_argument("--output", type=Path, required=True)
    compile_command.add_argument(
        "--manifest",
        type=Path,
        help="manifest path (default: OUTPUT.manifest.json in the same directory)",
    )
    compile_command.add_argument(
        "--time-anchor",
        required=True,
        help="timezone-aware ISO-8601 timestamp used as immutable compilation evidence",
    )
    compile_command.add_argument("--tokenizer-model")
    compile_command.add_argument("--tokenizer-revision")
    compile_command.add_argument(
        "--allow-tokenizer-download",
        action="store_true",
        help="permit the configured model tokenizer to be fetched",
    )
    compile_command.add_argument("--source-revision")
    compile_command.add_argument(
        "--source-adapter", choices=("repository", "incident"), default="repository"
    )
    compile_command.add_argument(
        "--security-policy",
        type=Path,
        help="M9 security policy (default: packaged contextc security policy)",
    )
    compile_command.add_argument("--system-instruction", default="")
    compile_command.add_argument("--developer-instruction", default="")
    compile_command.add_argument("--policy-instruction", default="")
    compile_command.add_argument("--tool-schema-text", default="")
    compile_command.add_argument("--json", action="store_true")
    compile_command.add_argument(
        "--incremental",
        action="store_true",
        help="reuse the local M8 content-addressed cache while preserving full-build semantics",
    )
    compile_command.add_argument(
        "--cache-root",
        type=Path,
        help="cache root (default: PATH/.contextc/cache)",
    )
    compile_command.add_argument(
        "--verify-incremental",
        action="store_true",
        help="also run a clean in-memory build and assert semantic equivalence",
    )

    cache = subparsers.add_parser("cache", help="inspect and invalidate the local M8 cache")
    cache.add_argument("--root", type=Path, default=Path(".contextc/cache"), help="cache root")
    cache_subparsers = cache.add_subparsers(dest="cache_command", required=True)
    cache_stats = cache_subparsers.add_parser("stats", help="show cache object/entry counts")
    cache_stats.add_argument("--json", action="store_true")
    cache_inspect = cache_subparsers.add_parser("inspect", help="inspect canonical cache metadata")
    cache_inspect.add_argument("--key")
    cache_inspect.add_argument("--json", action="store_true")
    cache_verify = cache_subparsers.add_parser(
        "verify", help="verify cache metadata and object hashes"
    )
    cache_verify.add_argument("--json", action="store_true")
    cache_plan = cache_subparsers.add_parser(
        "plan-invalidation", help="plan dependency-aware invalidation for a source URI"
    )
    cache_plan.add_argument("--source", required=True)
    cache_plan.add_argument("--json", action="store_true")
    cache_invalidate = cache_subparsers.add_parser(
        "invalidate", help="dry-run or apply dependency-aware source invalidation"
    )
    cache_invalidate.add_argument("--source", required=True)
    mode = cache_invalidate.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    cache_invalidate.add_argument("--json", action="store_true")

    mcp = subparsers.add_parser(
        "mcp", help="statically analyze MCP-style declarations and proposed call plans"
    )
    mcp_subparsers = mcp.add_subparsers(dest="mcp_command", required=True)

    mcp_live = mcp_subparsers.add_parser(
        "live", help="bounded local MCP validation over real stdio transport"
    )
    mcp_live_subparsers = mcp_live.add_subparsers(dest="mcp_live_command", required=True)
    for live_name in ("inspect", "tools", "resources", "validate"):
        live_parser = mcp_live_subparsers.add_parser(live_name)
        live_parser.add_argument("--server", type=Path, required=True)
        live_parser.add_argument("--sandbox", type=Path, default=Path(".contextc/live-mcp-sandbox"))
        live_parser.add_argument(
            "--timeout",
            type=float,
            default=5.0,
            help="MCP startup/initialization timeout in seconds",
        )
        live_parser.add_argument(
            "--operation-timeout",
            type=float,
            help="per-operation timeout in seconds (default: --timeout)",
        )
        if live_name == "validate":
            live_parser.add_argument("--cache-root", type=Path)
        live_parser.add_argument("--json", action="store_true")
    live_explain = mcp_live_subparsers.add_parser(
        "explain", help="explain stored live-MCP evidence without rerunning tools"
    )
    live_explain.add_argument("result", type=Path)
    live_explain.add_argument("--json", action="store_true")
    mcp_live_plan = mcp_live_subparsers.add_parser("plan")
    mcp_live_plan_subparsers = mcp_live_plan.add_subparsers(
        dest="mcp_live_plan_command", required=True
    )
    for live_plan_name in ("analyze", "execute"):
        live_plan_parser = mcp_live_plan_subparsers.add_parser(live_plan_name)
        live_plan_parser.add_argument("plan", type=Path)
        live_plan_parser.add_argument("--server", type=Path, required=True)
        live_plan_parser.add_argument(
            "--sandbox", type=Path, default=Path(".contextc/live-mcp-sandbox")
        )
        live_plan_parser.add_argument(
            "--timeout",
            type=float,
            default=5.0,
            help="MCP startup/initialization timeout in seconds",
        )
        live_plan_parser.add_argument(
            "--operation-timeout",
            type=float,
            help="per-operation timeout in seconds (default: --timeout)",
        )
        live_plan_parser.add_argument("--approval", type=Path, action="append", default=[])
        live_plan_parser.add_argument("--audit-output", type=Path)
        live_plan_parser.add_argument("--cache-root", type=Path)
        live_plan_parser.add_argument("--json", action="store_true")

    mcp_plan = mcp_subparsers.add_parser(
        "plan", help="validate/analyze a static proposed tool-call plan"
    )
    mcp_plan_subparsers = mcp_plan.add_subparsers(dest="mcp_plan_command", required=True)

    mcp_validate = mcp_plan_subparsers.add_parser(
        "validate", help="validate a plan and static tool/resource declarations"
    )
    mcp_validate.add_argument("plan", type=Path)
    mcp_validate.add_argument("--tools", type=Path, required=True)
    mcp_validate.add_argument("--json", action="store_true")

    mcp_analyze = mcp_plan_subparsers.add_parser(
        "analyze", help="statically analyze declared capability composition; no tool is executed"
    )
    mcp_analyze.add_argument("plan", type=Path)
    mcp_analyze.add_argument("--tools", type=Path, required=True)
    mcp_analyze.add_argument("--policy", type=Path)
    mcp_analyze.add_argument("--approval", type=Path, action="append", default=[])
    mcp_analyze.add_argument("--cache-root", type=Path)
    mcp_analyze.add_argument(
        "--output", type=Path, help="write the secret-safe capability manifest"
    )
    mcp_analyze.add_argument("--max-path-length", type=int, default=8)
    mcp_analyze.add_argument("--max-flows", type=int, default=64)
    mcp_analyze.add_argument("--json", action="store_true")

    mcp_explain = mcp_plan_subparsers.add_parser(
        "explain", help="explain one stored static capability flow"
    )
    mcp_explain.add_argument("analysis", type=Path)
    mcp_explain.add_argument("--flow", required=True)
    mcp_explain.add_argument("--json", action="store_true")

    reproduce = subparsers.add_parser(
        "reproduce", help="verify stored evidence or deterministically rebuild an artifact"
    )
    reproduce.add_argument("manifest", type=Path)
    reproduction_mode = reproduce.add_mutually_exclusive_group(required=True)
    reproduction_mode.add_argument("--verify", action="store_true")
    reproduction_mode.add_argument("--rebuild", action="store_true")
    reproduce.add_argument("--source", type=Path, help="explicit source repository")
    reproduce.add_argument("--source-revision")
    reproduce.add_argument("--output", type=Path, help="fresh rebuild artifact destination")
    reproduce.add_argument("--json", action="store_true")

    inspect = subparsers.add_parser("inspect", help="inspect stored M4 build evidence")
    inspect.add_argument("manifest", type=Path)
    inspect.add_argument("--json", action="store_true")

    explain = subparsers.add_parser("explain", help="explain a build from stored M4/M9 evidence")
    explain.add_argument("manifest", type=Path)
    explain.add_argument("--node", help="show stored security/selection evidence for one node")
    explain.add_argument("--json", action="store_true")

    benchmark = subparsers.add_parser(
        "benchmark", help="run and inspect isolated M6 benchmark evidence"
    )
    benchmark_subparsers = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_run = benchmark_subparsers.add_parser("run", help="run one physical benchmark task")
    benchmark_run.add_argument("task", type=Path)
    benchmark_run.add_argument("--database", type=Path, required=True)
    benchmark_run.add_argument("--strategy", action="append", default=[])
    benchmark_debug = benchmark_subparsers.add_parser(
        "debug", help="show canonical label/IR/selection alignment for one task"
    )
    benchmark_debug.add_argument("task", type=Path)
    benchmark_debug.add_argument("--strategy", action="append", default=[])
    benchmark_suite = benchmark_subparsers.add_parser(
        "suite", help="run a controlled physical benchmark suite"
    )
    benchmark_suite.add_argument("suite", type=Path)
    benchmark_suite.add_argument("--database", type=Path, required=True)
    benchmark_suite.add_argument("--strategy", action="append", default=[])
    benchmark_inspect = benchmark_subparsers.add_parser(
        "inspect", help="inspect stored benchmark or Top-K trace evidence"
    )
    benchmark_inspect.add_argument("database", type=Path)
    benchmark_inspect.add_argument("--run-id")
    benchmark_inspect.add_argument("--json", action="store_true")
    benchmark_report = benchmark_subparsers.add_parser(
        "report", help="print raw per-task, per-strategy metric rows"
    )
    benchmark_report.add_argument("database", type=Path)

    case_study = subparsers.add_parser(
        "case-study", help="run the offline M11 python-humanize historical case study"
    )
    case_subparsers = case_study.add_subparsers(dest="case_study_command", required=True)
    case_subparsers.add_parser("list", help="list packaged public historical tasks")
    case_validate = case_subparsers.add_parser(
        "validate", help="validate historical revisions, labels, reviews, and diversity"
    )
    case_validate.add_argument("--all", action="store_true", required=True)
    case_extract = case_subparsers.add_parser(
        "extract-labels", help="show fix-diff candidates without approving ground truth"
    )
    case_extract.add_argument("task")
    case_run = case_subparsers.add_parser(
        "run", help="run equal-footing strategies against exact pre-fix revisions"
    )
    case_run_group = case_run.add_mutually_exclusive_group(required=True)
    case_run_group.add_argument("--all", action="store_true")
    case_run_group.add_argument("--task")
    case_run.add_argument("--database", type=Path, default=Path(".contextc/case-study.sqlite3"))
    case_run.add_argument("--strategy", action="append", default=[])
    case_report = case_subparsers.add_parser(
        "report", help="emit the complete raw case-study table and bounded summary"
    )
    case_report.add_argument("--database", type=Path, default=Path(".contextc/case-study.sqlite3"))
    case_report.add_argument("--markdown", action="store_true")
    case_report.add_argument("--output", type=Path)
    case_determinism = case_subparsers.add_parser(
        "verify-determinism", help="repeat tasks and reverse physical file creation order"
    )
    case_determinism_group = case_determinism.add_mutually_exclusive_group(required=True)
    case_determinism_group.add_argument("--all", action="store_true")
    case_determinism_group.add_argument("--task")
    case_determinism.add_argument("--strategy", action="append", default=[])

    policy = subparsers.add_parser("policy", help="validate M9 structural security policies")
    policy_subparsers = policy.add_subparsers(dest="policy_command", required=True)
    policy_validate = policy_subparsers.add_parser("validate", help="validate a security policy")
    policy_validate.add_argument("policy", type=Path)
    policy_validate.add_argument("--json", action="store_true")

    security = subparsers.add_parser(
        "security", help="scan retained static sources using M9 policy and taint analysis"
    )
    security_subparsers = security.add_subparsers(dest="security_command", required=True)
    security_scan = security_subparsers.add_parser(
        "scan", help="scan a static MCP-shaped JSON result"
    )
    security_scan.add_argument("source", type=Path)
    security_scan.add_argument("--policy", type=Path)
    security_scan.add_argument("--json", action="store_true")
    security_explain = security_subparsers.add_parser(
        "explain",
        help="explain stored-in-memory analysis for a static MCP-shaped JSON result",
    )
    security_explain.add_argument("source", type=Path)
    security_explain.add_argument("--policy", type=Path)
    security_explain.add_argument("--json", action="store_true")

    demo = subparsers.add_parser("demo", help="run packaged M15 cross-domain incident demos")
    demo_subparsers = demo.add_subparsers(dest="demo_command", required=True)
    demo_subparsers.add_parser("list", help="list packaged offline demos")
    demo_validate = demo_subparsers.add_parser("validate", help="validate an incident demo")
    demo_validate.add_argument("incident")
    demo_compile = demo_subparsers.add_parser("compile", help="compile an incident demo")
    demo_compile.add_argument("incident")
    demo_compile.add_argument("--strategy", default="auto")
    demo_compile.add_argument("--budget", type=int, default=4000)
    demo_compile.add_argument("--target", choices=("structured-json",), default="structured-json")
    demo_compile.add_argument("--output", type=Path)
    demo_compile.add_argument("--json", action="store_true")
    demo_compare = demo_subparsers.add_parser("compare", help="compare equal-footing strategies")
    demo_compare.add_argument("incident")
    demo_compare.add_argument("--all-strategies", action="store_true")
    demo_compare.add_argument("--strategy", action="append", default=[])
    demo_compare.add_argument("--budget", type=int, default=4000)
    demo_compare.add_argument("--json", action="store_true")
    demo_graph = demo_subparsers.add_parser("graph", help="inspect the incident context graph")
    demo_graph.add_argument("incident")
    demo_graph.add_argument("--selected-only", action="store_true")
    demo_graph.add_argument("--strategy", default="auto")
    demo_graph.add_argument("--budget", type=int, default=4000)
    demo_graph.add_argument("--json", action="store_true")
    demo_explain = demo_subparsers.add_parser(
        "explain", help="explain incident selection/security/supersession"
    )
    demo_explain.add_argument("incident")
    demo_explain.add_argument("--source", required=True)
    demo_explain.add_argument("--strategy", default="auto")
    demo_explain.add_argument("--budget", type=int, default=4000)
    demo_explain.add_argument("--json", action="store_true")
    demo_reproduce = demo_subparsers.add_parser(
        "reproduce", help="verify and rebuild an incident demo"
    )
    demo_reproduce.add_argument("incident")
    demo_reproduce.add_argument("--strategy", default="auto")
    demo_reproduce.add_argument("--budget", type=int, default=4000)
    demo_reproduce.add_argument("--json", action="store_true")

    demo_registry = demo_subparsers.add_parser(
        "registry", help="inspect the packaged M16 release-demo registry"
    )
    demo_registry_subparsers = demo_registry.add_subparsers(
        dest="demo_registry_command", required=True
    )
    demo_registry_subparsers.add_parser("list", help="list packaged release demos")
    demo_registry_subparsers.add_parser(
        "verify", help="verify registry schema and packaged resource integrity"
    )
    demo_verify_release = demo_subparsers.add_parser(
        "verify", help="verify packaged release demos semantically"
    )
    demo_verify_release.add_argument("demo_id", nargs="?")
    demo_verify_release.add_argument("--all", action="store_true")
    demo_run_release = demo_subparsers.add_parser(
        "run", help="run one bounded packaged release demo"
    )
    demo_run_release.add_argument("demo_id")
    demo_run_release.add_argument("--strategy")
    demo_run_release.add_argument("--budget", type=int)
    demo_run_release.add_argument("--target", choices=("generic", "structured-json"))
    demo_run_release.add_argument("--json", action="store_true")

    ui = subparsers.add_parser("ui", help="launch the optional local read-only Observatory")
    ui.add_argument("--address", default="127.0.0.1")
    ui.add_argument("--port", type=int, default=8501)
    return parser


def _print_json(value: object) -> None:
    print(json.dumps(to_canonical_primitive(value), ensure_ascii=False, indent=2, sort_keys=True))


def _run_doctor(arguments: argparse.Namespace) -> int:
    _config, checks = doctor_report(base_path=Path.cwd(), config_path=arguments.config)
    if arguments.json:
        _print_json({"checks": checks, "schema_version": 1})
    else:
        for check in checks:
            status = "ok" if check.ok else "failed"
            print(f"{status:6} {check.name}: {check.detail}")
    return 0 if all(check.ok for check in checks) else 1


def _configuration_for_repository(path: Path, arguments: argparse.Namespace) -> ProjectConfig:
    contextc_path = path / "contextc.toml"
    pyproject_path = path / "pyproject.toml"
    if contextc_path.is_file():
        config_path: Path | None = contextc_path
    elif pyproject_path.is_file():
        config_path = pyproject_path
    else:
        config_path = None
    config = load_project_config(config_path)
    return apply_cli_overrides(
        config,
        {
            "max_file_bytes": arguments.max_file_bytes,
            "include_hidden": arguments.include_hidden,
        },
    )


def _run_index(arguments: argparse.Namespace) -> int:
    config = _configuration_for_repository(arguments.path, arguments)
    policy = IndexPolicy(
        max_file_bytes=config.max_file_bytes,
        include_hidden=config.include_hidden,
    )
    result = RepositoryParser(policy, source_rules=config.source_rules).parse(arguments.path)
    if arguments.json:
        _print_json(result)
    else:
        print(f"indexed {result.files_considered} files into {len(result.nodes)} nodes")
        print(f"diagnostics: {len(result.diagnostics)}")
    return 0


def _parse_time_anchor(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("--time-anchor must include a UTC offset or Z")
    return parsed


def _run_compile(arguments: argparse.Namespace) -> int:
    # Keep all lowering and optional tokenizer modules outside CLI startup.
    from contextc.application.compile import (
        CompileRepositoryRequest,
        compile_source_to_path,
    )
    from contextc.optimization.models import OptimizerConfiguration
    from contextc.reproduction import read_build_manifest
    from contextc.reproduction.transaction import default_manifest_path
    from contextc.security import load_policy
    from contextc.source_rules import SourceFactRule
    from contextc.targets import TargetId, TargetManifestFields

    source_rules: tuple[SourceFactRule, ...] = ()
    if arguments.source_adapter == "repository":
        config_path = arguments.path / "contextc.toml"
        pyproject_path = arguments.path / "pyproject.toml"
        if config_path.is_file():
            source_rules = load_project_config(config_path).source_rules
        elif pyproject_path.is_file():
            source_rules = load_project_config(pyproject_path).source_rules

    request = CompileRepositoryRequest(
        repository=arguments.path,
        task=arguments.task,
        target_id=TargetId(arguments.target),
        token_budget=arguments.token_budget,
        time_anchor=_parse_time_anchor(arguments.time_anchor),
        tokenizer_model_id=arguments.tokenizer_model,
        tokenizer_revision=arguments.tokenizer_revision,
        tokenizer_local_files_only=not arguments.allow_tokenizer_download,
        source_revision=arguments.source_revision,
        system_instruction=arguments.system_instruction,
        developer_instruction=arguments.developer_instruction,
        policy_instruction=arguments.policy_instruction,
        tool_schema_text=arguments.tool_schema_text,
        security_policy=load_policy(arguments.security_policy),
        source_adapter_id=arguments.source_adapter,
        source_rules=source_rules,
        optimizer=OptimizerConfiguration(
            requested_strategy=arguments.optimizer,
            source_content_allowance=arguments.source_content_allowance,
            mandatory_node_ids=tuple(arguments.mandatory_node),
            blocked_node_ids=tuple(arguments.block_node),
        ),
    )
    manifest_path = (
        default_manifest_path(arguments.output)
        if arguments.manifest is None
        else arguments.manifest
    )
    cache_report = None
    equivalence = None
    if arguments.incremental:
        from contextc.incremental import IncrementalCompileRequest, IncrementalService

        incremental = IncrementalService().build(
            IncrementalCompileRequest(
                compile_request=request,
                output_path=arguments.output,
                manifest_path=manifest_path,
                cache_root=arguments.cache_root,
                verify_against_clean=arguments.verify_incremental,
            )
        )
        result = incremental.compilation
        cache_report = incremental.cache_report
        equivalence = incremental.equivalence
    else:
        result = compile_source_to_path(
            request,
            arguments.output,
            manifest_path=manifest_path,
        )
    manifest = read_build_manifest(manifest_path.resolve())
    rendered = result.rendered
    if arguments.json:
        _print_json(
            {
                "output": str(arguments.output.resolve()),
                "manifest": str(manifest_path.resolve()),
                "build_id": manifest.build_id,
                "artifact_content_identity": manifest.artifact_content_identity,
                "manifest_fields": TargetManifestFields.from_rendered(rendered),
                "budget_evidence": rendered.budget_evidence,
                "trim_evidence": rendered.trim_evidence,
                "optimizer": result.selection,
                "supersession": {
                    "policy_identity": result.supersession.policy_identity,
                    "superseded_node_ids": result.supersession.superseded_node_ids,
                    "superseding_node_by_id": result.supersession.superseding_node_by_id,
                    "diagnostic_codes": tuple(
                        item.code.value for item in result.supersession.diagnostics
                    ),
                },
                "security": {
                    "analysis_version": result.security.analysis_version,
                    "diagnostic_codes": tuple(
                        diagnostic.code.value for diagnostic in result.security.diagnostics
                    ),
                    "excluded_node_ids": result.security.excluded_node_ids,
                    "policy_identity": result.security.policy_identity,
                    "rule_ids_triggered": tuple(
                        sorted({decision.rule_id for decision in result.security.decisions})
                    ),
                    "token_deltas": result.security_token_deltas,
                    "transformations": result.security.transformations,
                },
                "cache": None if cache_report is None else cache_report.to_dict(),
                "incremental_equivalence": (
                    None
                    if equivalence is None
                    else {
                        "equivalent": equivalence.equivalent,
                        "differences": equivalence.differences,
                    }
                ),
            }
        )
    else:
        print(f"compiled {len(rendered.ordered_node_ids)} nodes for {rendered.target_id.value}")
        print(f"tokens: {rendered.exact_token_count}/{rendered.budget_evidence.configured_budget}")
        print(
            "optimizer: "
            f"{result.selection.requested_strategy_id} -> {result.selection.strategy_id} "
            f"({result.selection.optimizer_status.value})"
        )
        print(f"output: {arguments.output.resolve()}")
        print(f"manifest: {manifest_path.resolve()}")
        print(f"build: {manifest.build_id}")
        if cache_report is not None:
            print(
                f"cache: reused={len(cache_report.reused)} "
                f"recomputed={len(cache_report.recomputed)}"
            )
        if equivalence is not None:
            print(f"incremental/full equivalent: {equivalence.equivalent}")
    return 0


def _run_cache(arguments: argparse.Namespace) -> int:
    from contextc.cache.service import CacheService

    service = CacheService(arguments.root)
    command = arguments.cache_command
    value: object
    if command == "stats":
        value = service.stats()
    elif command == "inspect":
        value = service.inspect(arguments.key)
    elif command == "verify":
        problems = service.verify()
        value = {"valid": not problems, "problems": problems}
    elif command == "plan-invalidation":
        plan = service.plan_invalidation(arguments.source)
        value = {
            "source_uri": plan.source_uri,
            "root_key_identities": plan.root_key_identities,
            "affected_key_identities": plan.affected_key_identities,
            "applied": False,
        }
    elif command == "invalidate":
        apply = bool(arguments.apply)
        plan = service.invalidate_source(arguments.source, apply=apply)
        value = {
            "source_uri": plan.source_uri,
            "root_key_identities": plan.root_key_identities,
            "affected_key_identities": plan.affected_key_identities,
            "applied": apply,
        }
    else:
        raise ValueError(f"unknown cache command {command!r}")
    if getattr(arguments, "json", False):
        _print_json(value)
    else:
        print(json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True))
    return 0


def _run_live_mcp(arguments: argparse.Namespace) -> int:
    from contextc.capabilities.approval import load_approval
    from contextc.capabilities.plan import load_plan, plan_from_mapping
    from contextc.live_mcp.models import LiveExecutionDecision
    from contextc.live_mcp.service import LiveMCPValidationService

    command = arguments.mcp_live_command
    if command == "explain":
        from contextc.live_mcp.explain import explain_live_result

        raw = json.loads(arguments.result.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("live MCP result must be a JSON object")
        value = explain_live_result(raw)
        _print_json(value) if arguments.json else print(
            json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True)
        )
        return 0
    service = LiveMCPValidationService(cache_root=getattr(arguments, "cache_root", None))
    spec = service.fixture_spec(
        arguments.server,
        arguments.sandbox,
        timeout_seconds=arguments.timeout,
        operation_timeout_seconds=getattr(arguments, "operation_timeout", None),
    )
    if command in {"inspect", "tools", "resources"}:
        inspection = service.inspect_server(spec)
        if command == "inspect":
            value = inspection.to_dict()
        elif command == "tools":
            value = {
                "server_id": inspection.server_id,
                "transport": inspection.transport,
                "tools": to_canonical_primitive(inspection.tools),
            }
        else:
            value = {
                "server_id": inspection.server_id,
                "transport": inspection.transport,
                "resources": to_canonical_primitive(inspection.resources),
            }
        _print_json(value) if arguments.json else print(
            json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True)
        )
        return 0
    if command == "validate":
        plans = (
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "public-read",
                    "calls": [{"call_id": "read", "tool_id": "read_public_note"}],
                }
            ),
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "public-to-local",
                    "calls": [
                        {"call_id": "read", "tool_id": "read_public_note"},
                        {
                            "call_id": "write",
                            "tool_id": "write_local_note",
                            "input_bindings": {"content": "call:read.output"},
                            "literal_inputs": {"relative_name": "copied-public.txt"},
                        },
                    ],
                }
            ),
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "secret-to-message",
                    "calls": [
                        {"call_id": "read-secret", "tool_id": "read_secret_note"},
                        {
                            "call_id": "send",
                            "tool_id": "post_external_message",
                            "input_bindings": {"message": "call:read-secret.output"},
                        },
                    ],
                }
            ),
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "untrusted-to-execution",
                    "calls": [
                        {"call_id": "source", "tool_id": "echo_untrusted_text"},
                        {
                            "call_id": "sink",
                            "tool_id": "execute_fake_command",
                            "input_bindings": {"command": "call:source.output"},
                        },
                    ],
                }
            ),
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "credential-to-network",
                    "calls": [
                        {"call_id": "credential", "tool_id": "read_test_credential"},
                        {
                            "call_id": "network",
                            "tool_id": "fake_http_post",
                            "input_bindings": {"payload": "call:credential.output"},
                            "literal_inputs": {"destination": "https://example.invalid/test"},
                        },
                    ],
                }
            ),
            plan_from_mapping(
                {
                    "schema_version": {"major": 1, "minor": 0},
                    "plan_id": "declaration-mismatch",
                    "calls": [{"call_id": "read", "tool_id": "misdeclared_reader"}],
                }
            ),
        )
        validation_result = service.run_validation_suite(spec, plans)
        value = validation_result.to_dict()
        _print_json(value) if arguments.json else print(
            json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True)
        )
        return (
            0
            if validation_result.synthetic_secret_leaks == 0
            and validation_result.real_external_network_calls == 0
            and validation_result.real_shell_commands == 0
            else 3
        )
    if command != "plan":
        raise ValueError(f"unknown live MCP command {command!r}")
    plan = load_plan(arguments.plan)
    approvals = tuple(load_approval(path) for path in arguments.approval)
    inspection = service.inspect_server(spec)
    if arguments.mcp_live_plan_command == "analyze":
        manifest = service.analyze_plan(
            inspection, plan, approvals=approvals, fixture_version=spec.fixture_version
        )
        value = {
            "mode": "live_declarations_static_analysis",
            "transport": "stdio",
            "server_id": inspection.server_id,
            "server_declaration_hash": inspection.server_declaration_hash,
            "sink_execution_performed": False,
            "static_manifest": manifest.to_dict(),
        }
        _print_json(value) if arguments.json else print(
            json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True)
        )
        return 3 if manifest.blocked else 0
    execution_result = service.execute_validated_plan(
        spec, plan, approvals=approvals, audit_path=arguments.audit_output
    )
    value = execution_result.to_dict()
    _print_json(value) if arguments.json else print(
        json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True)
    )
    return 0 if execution_result.decision is LiveExecutionDecision.ALLOW else 3


def _run_mcp(arguments: argparse.Namespace) -> int:
    """Run static M10a plan validation/analysis/explanation. No tool execution exists here."""

    from contextc.capabilities.approval import load_approval
    from contextc.capabilities.cache import manifest_from_mapping
    from contextc.capabilities.mcp_tools import load_declaration_directory
    from contextc.capabilities.models import CapabilityLimits
    from contextc.capabilities.plan import load_plan
    from contextc.capabilities.policy import load_policy as load_capability_policy
    from contextc.capabilities.service import CapabilityService

    if arguments.mcp_command == "live":
        return _run_live_mcp(arguments)
    if arguments.mcp_command != "plan":
        raise ValueError(f"unknown MCP command {arguments.mcp_command!r}")
    command = arguments.mcp_plan_command
    if command == "explain":
        raw = json.loads(arguments.analysis.read_text(encoding="utf-8"))
        if not isinstance(raw, Mapping):
            raise ValueError("capability analysis artifact must be a JSON object")
        manifest = manifest_from_mapping(raw)
        value = CapabilityService().explain_flow(manifest, arguments.flow)
        if arguments.json:
            _print_json(value)
        else:
            print("static capability-flow explanation (no tool was executed)")
            print(json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True))
        return 0

    plan = load_plan(arguments.plan)
    tools, resources = load_declaration_directory(arguments.tools)
    if command == "validate":
        result = CapabilityService().validate_plan(plan, tools, resources)
        value = {
            "analysis_mode": "static",
            "tool_execution_performed": False,
            "valid": result.valid,
            "diagnostics": [diagnostic.to_dict() for diagnostic in result.diagnostics],
        }
        if arguments.json:
            _print_json(value)
        else:
            print("static capability-plan validation (no tool was executed)")
            print(json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True))
        return 0 if result.valid else 2

    if command != "analyze":
        raise ValueError(f"unknown MCP plan command {command!r}")
    policy = load_capability_policy(arguments.policy)
    approvals = tuple(load_approval(path) for path in arguments.approval)
    limits = CapabilityLimits(
        max_path_length=arguments.max_path_length,
        max_reported_flows=arguments.max_flows,
    )
    manifest = CapabilityService(cache_root=arguments.cache_root).analyze_plan(
        plan,
        tools,
        resources,
        policy,
        approvals=approvals,
        limits=limits,
    )
    value = manifest.to_dict()
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(
            json.dumps(to_canonical_primitive(value), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    if arguments.json:
        _print_json(value)
    else:
        print("static capability analysis only; no tool was executed")
        print(f"plan: {manifest.plan_id}")
        print(f"policy: {manifest.policy_id}@{manifest.policy_version}")
        print(f"flows: {len(manifest.flows)}")
        print(f"blocked: {manifest.blocked}")
        print(f"pending approval: {manifest.pending_approval}")
        print(f"cache: {manifest.cache_status}")
        for diagnostic in manifest.diagnostics:
            print(f"{diagnostic.code.value}: {diagnostic.message}")
        if arguments.output is not None:
            print(f"analysis: {arguments.output}")
    return 3 if manifest.blocked else 0


def _run_reproduce(arguments: argparse.Namespace) -> int:
    from contextc.reproduction import rebuild_build, verify_build

    if arguments.verify:
        result = verify_build(
            arguments.manifest,
            source_root=arguments.source,
            source_revision=arguments.source_revision,
        )
        evidence = {
            "artifact_content_identity": result.artifact_identity,
            "artifact_path": str(result.artifact_path),
            "final_token_count": result.final_token_count,
            "manifest_path": str(result.manifest_path),
            "source_checked": result.source_checked,
            "status": result.status,
        }
        if arguments.json:
            _print_json(evidence)
        else:
            print("verified")
            print(f"artifact: {result.artifact_path}")
            print(f"identity: {result.artifact_identity}")
            print(f"tokens: {result.final_token_count}")
            print(f"source checked: {result.source_checked}")
        return 0
    if arguments.output is None:
        raise ValueError("--rebuild requires --output DEST")
    rebuilt = rebuild_build(
        arguments.manifest,
        output_path=arguments.output,
        source_root=arguments.source,
        source_revision=arguments.source_revision,
    )
    evidence = {
        "artifact_content_identity": rebuilt.artifact_identity,
        "artifact_path": str(rebuilt.artifact_path),
        "build_id": rebuilt.build_id,
        "final_token_count": rebuilt.final_token_count,
        "manifest_path": str(rebuilt.manifest_path),
        "status": "rebuilt",
    }
    if arguments.json:
        _print_json(evidence)
    else:
        print("rebuilt and matched stored semantic evidence")
        print(f"artifact: {rebuilt.artifact_path}")
        print(f"manifest: {rebuilt.manifest_path}")
        print(f"identity: {rebuilt.artifact_identity}")
        print(f"tokens: {rebuilt.final_token_count}")
    return 0


def _run_stored_evidence(arguments: argparse.Namespace, *, explain: bool) -> int:
    from contextc.reproduction import stored_build_evidence

    evidence = stored_build_evidence(arguments.manifest)
    if explain and getattr(arguments, "node", None):
        node_id = cast(str, arguments.node)
        security = cast(Mapping[str, object], evidence["security_evidence"])
        node_facts = cast(Mapping[str, object], security["node_facts"])
        if node_id not in node_facts:
            raise ValueError(f"stored build has no node {node_id!r}")
        decision_items = cast(tuple[Mapping[str, object], ...], security["decisions"])
        decisions = tuple(
            decision for decision in decision_items if decision.get("node_id") == node_id
        )
        transformations = cast(Mapping[str, object], security["transformations"])
        token_deltas = cast(Mapping[str, object], security["token_deltas"])
        evidence = {
            "node_id": node_id,
            "source_facts": node_facts[node_id],
            "security_decisions": decisions,
            "security_transformations": transformations.get(node_id, ()),
            "security_token_delta": token_deltas.get(node_id),
            "selected_after_security": node_id
            in cast(tuple[str, ...], evidence["optimizer_selected_node_ids"]),
            "excluded_by_security": node_id in cast(tuple[str, ...], security["excluded_node_ids"]),
            "security_policy": {
                "analysis_version": security["analysis_version"],
                "policy_id": security["policy_id"],
                "policy_identity": security["policy_identity"],
                "policy_version": security["policy_version"],
            },
            "relationship_diagnostics": tuple(
                item
                for item in cast(tuple[Mapping[str, object], ...], evidence["diagnostic_evidence"])
                if node_id in cast(tuple[str, ...], item.get("node_ids", ()))
                and item.get("code") in {"CTX200", "CTX210"}
            ),
        }
    if arguments.json:
        _print_json(evidence)
        return 0
    heading = "Stored build explanation" if explain else "Stored build inspection"
    print(heading)
    for key, value in evidence.items():
        rendered = (
            (", ".join(cast(tuple[str, ...], value)) if value else "none")
            if key == "diagnostics"
            else str(value)
        )
        print(f"{key}: {rendered}")
    return 0


def _run_benchmark(arguments: argparse.Namespace) -> int:
    from contextc.benchmark.service import debug_task, run_suite, run_task
    from contextc.benchmark.storage import BenchmarkStore

    strategies = tuple(arguments.strategy) if hasattr(arguments, "strategy") else ()
    if arguments.benchmark_command == "debug":
        report = debug_task(arguments.task, strategies=strategies or ("naive", "density_greedy"))
        _print_json(report)
        return 0
    store = BenchmarkStore(arguments.database)
    if arguments.benchmark_command == "run":
        runs = run_task(arguments.task, strategies=strategies or ("auto",), store=store)
        _print_json(
            {
                "runs": [
                    {
                        "run_id": run.run_id,
                        "task_id": run.task_id,
                        "strategy_id": run.strategy_id,
                        "optimizer_status": run.optimizer_status,
                        "metrics": run.metrics,
                    }
                    for run in runs
                ]
            }
        )
        return 0
    if arguments.benchmark_command == "suite":
        reports = run_suite(
            arguments.suite,
            strategies=strategies or ("naive", "density_greedy", "brute_force"),
            store=store,
        )
        _print_json({"tasks": reports})
        return 0 if all(item["status"] in {"completed", "infeasible"} for item in reports) else 2
    if arguments.benchmark_command == "report":
        _print_json({"rows": store.raw_metric_rows()})
        return 0
    if arguments.run_id:
        evidence = store.load_run_evidence(arguments.run_id)
    else:
        evidence = {"runs": store.list_runs()}
    _print_json(evidence)
    return 0


def _run_case_study(arguments: argparse.Namespace) -> int:
    from contextc.benchmark.storage import BenchmarkStore
    from contextc.case_study.analysis import validate_suite
    from contextc.case_study.executor import (
        run_case_suite,
        run_case_task,
        verify_task_determinism,
    )
    from contextc.case_study.extract_labels import extract_label_candidates
    from contextc.case_study.loader import (
        list_task_directories,
        load_public_case_task,
        resolve_task_directory,
    )
    from contextc.case_study.reporting import build_report, report_markdown

    command = arguments.case_study_command
    if command == "list":
        tasks = tuple(load_public_case_task(path) for path in list_task_directories())
        _print_json(
            {
                "tasks": tuple(
                    {
                        "task_id": task.task_id,
                        "description": task.description,
                        "pre_fix_revision": task.pre_fix_revision,
                        "token_budget": task.token_budget,
                        "source_content_allowance": task.source_content_allowance,
                    }
                    for task in tasks
                )
            }
        )
        return 0
    if command == "validate":
        validations = validate_suite()
        _print_json({"repository": "python-humanize", "tasks": validations})
        return 0
    if command == "extract-labels":
        _print_json(extract_label_candidates(resolve_task_directory(arguments.task)))
        return 0
    strategies = tuple(arguments.strategy) if hasattr(arguments, "strategy") else ()
    if command == "run":
        store = BenchmarkStore(arguments.database)
        if arguments.all:
            executions = run_case_suite(strategies=strategies, store=store)
        else:
            executions = (
                run_case_task(
                    resolve_task_directory(arguments.task),
                    strategies=strategies,
                    store=store,
                ),
            )
        _print_json(
            {
                "database": str(arguments.database.resolve()),
                "tasks": tuple(
                    {
                        "task_id": execution.task.public.task_id,
                        "runs": tuple(run.run_id for run in execution.runs),
                        "reference_bundle_unchanged": execution.reference_bundle_unchanged,
                        "evaluator_sentinel_absent": execution.evaluator_sentinel_absent,
                    }
                    for execution in executions
                ),
            }
        )
        return 0
    if command == "report":
        report = build_report(arguments.database)
        rendered = (
            report_markdown(report)
            if arguments.markdown
            else json.dumps(
                to_canonical_primitive(report), ensure_ascii=False, indent=2, sort_keys=True
            )
        )
        if arguments.output is None:
            print(rendered)
        else:
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(rendered + ("" if rendered.endswith("\n") else "\n"))
            print(f"report: {arguments.output.resolve()}")
        return 0
    task_directories = (
        list_task_directories() if arguments.all else (resolve_task_directory(arguments.task),)
    )
    reports = tuple(
        verify_task_determinism(path, strategies=strategies) for path in task_directories
    )
    _print_json({"tasks": reports})
    return (
        0
        if all(
            report.repeated_semantics_identical and report.reversed_materialization_identical
            for report in reports
        )
        else 2
    )


def _run_policy(arguments: argparse.Namespace) -> int:
    from contextc.security.policy import load_policy, policy_identity

    policy = load_policy(arguments.policy)
    payload = {
        "policy_id": policy.policy_id,
        "version": policy.version,
        "identity": policy_identity(policy),
        "rules": tuple(rule.rule_id for rule in policy.rules),
        "valid": True,
    }
    if arguments.json:
        _print_json(payload)
    else:
        print(f"valid policy {policy.policy_id}@{policy.version}")
        print(f"identity: {payload['identity']}")
        print(f"rules: {len(policy.rules)}")
    return 0


def _security_payload(result: object) -> dict[str, object]:
    from contextc.security.models import SecurityResult

    if not isinstance(result, SecurityResult):
        raise AssertionError("unexpected security result")
    return {
        "policy_id": result.policy_id,
        "policy_version": result.policy_version,
        "policy_identity": result.policy_identity,
        "analysis_version": result.analysis_version,
        "blocked": result.blocked,
        "blocked_node_ids": result.blocked_node_ids,
        "excluded_node_ids": result.excluded_node_ids,
        "diagnostics": result.diagnostics,
        "decisions": result.decisions,
        "taint_paths": result.taint_paths,
        "transformations": result.transformations,
        "nodes": result.nodes,
    }


def _run_security(arguments: argparse.Namespace) -> int:
    from contextc.security.service import SecurityService

    result = SecurityService.from_policy_path(arguments.policy).scan_mcp_file(arguments.source)
    payload = _security_payload(result)
    if arguments.security_command == "scan":
        if arguments.json:
            _print_json(payload)
        else:
            print(f"policy: {result.policy_id}@{result.policy_version}")
            print(f"blocked: {str(result.blocked).lower()}")
            for diagnostic in result.diagnostics:
                print(f"{diagnostic.code.value} {diagnostic.message}")
            for decision in result.decisions:
                print(f"{decision.rule_id}: {decision.node_id} -> {decision.action.value}")
    else:
        explanation = {
            "policy": f"{result.policy_id}@{result.policy_version}",
            "policy_identity": result.policy_identity,
            "analysis_version": result.analysis_version,
            "source": str(arguments.source),
            "nodes": tuple(
                {
                    "node_id": node.node_id,
                    "source_uri": node.source.uri,
                    "trust_domain": node.trust_domain.value,
                    "sensitivity": node.sensitivity.value,
                    "instruction_authority": node.instruction_authority.value,
                    "transformations": node.transformations,
                }
                for node in result.nodes
            ),
            "decisions": tuple(
                {
                    "node_id": decision.node_id,
                    "rule_id": decision.rule_id,
                    "action": decision.action.value,
                    "diagnostic_code": decision.diagnostic_code,
                    "taint_path": (None if decision.taint_path is None else decision.taint_path),
                }
                for decision in result.decisions
            ),
            "diagnostic_codes": tuple(diagnostic.code.value for diagnostic in result.diagnostics),
            "transformations": result.transformations,
            "blocked": result.blocked,
        }
        if arguments.json:
            _print_json(explanation)
        else:
            _print_json(explanation)
    return 3 if result.blocked else 0


def _run_demo(arguments: argparse.Namespace) -> int:
    if arguments.demo_command in {"registry", "verify", "run"}:
        from contextc.release_demos.service import DemoService

        service = DemoService()
        if arguments.demo_command == "registry":
            if arguments.demo_registry_command == "list":
                _print_json({"registry_id": service.registry_id, "demos": service.list_demos()})
                return 0
            registry_result = service.verify_registry()
            _print_json(registry_result)
            return 0 if registry_result.valid else 2
        if arguments.demo_command == "verify":
            if arguments.all:
                all_verification = service.verify_all()
                _print_json(all_verification)
                return 0 if all_verification.valid else 2
            if not arguments.demo_id:
                raise ValueError("demo verify requires DEMO_ID or --all")
            demo_verification = service.verify_demo(arguments.demo_id)
            _print_json(demo_verification)
            return 0 if demo_verification.valid else 2
        demo_result = service.run_demo(
            arguments.demo_id,
            strategy=arguments.strategy,
            budget=arguments.budget,
            target=arguments.target,
        )
        _print_json(demo_result)
        return 0

    from contextc.cross_domain.service import (
        DEFAULT_STRATEGIES,
        compare_strategies,
        comparison_payload,
        compile_demo,
        explain_demo,
        graph_demo,
        list_demos,
        reproduce_demo,
        validate_demo,
    )
    from contextc.targets import TargetId

    command = arguments.demo_command
    if command == "list":
        _print_json({"demos": list_demos()})
        return 0
    if command == "validate":
        _print_json(validate_demo(arguments.incident))
        return 0
    if command == "compile":
        compiled = compile_demo(
            arguments.incident,
            strategy=arguments.strategy,
            budget=arguments.budget,
            target=TargetId(arguments.target),
            output_path=arguments.output,
        )
        compilation = compiled.compilation
        payload = {
            "demo_id": compiled.demo_id,
            "output": compiled.output_path,
            "manifest": compiled.manifest_path,
            "target": compilation.rendered.target_id.value,
            "final_token_count": compilation.rendered.exact_token_count,
            "token_budget": compilation.rendered.budget_evidence.configured_budget,
            "selected_node_ids": compilation.rendered.ordered_node_ids,
            "optimizer_status": compilation.selection.optimizer_status.value,
            "optimizer_used": compilation.selection.strategy_id,
            "superseded_node_ids": compilation.supersession.superseded_node_ids,
            "diagnostic_codes": tuple(
                item.code.value
                for item in (
                    *compilation.supersession.diagnostics,
                    *compilation.conflicts.diagnostics,
                    *compilation.security.diagnostics,
                )
            ),
            "security_actions": tuple(
                {
                    "node_id": item.node_id,
                    "rule_id": item.rule_id,
                    "action": item.action.value,
                }
                for item in compilation.security.decisions
            ),
        }
        _print_json(payload)
        return 0
    if command == "compare":
        strategies = (
            DEFAULT_STRATEGIES
            if arguments.all_strategies or not arguments.strategy
            else tuple(arguments.strategy)
        )
        _print_json(
            comparison_payload(
                compare_strategies(
                    arguments.incident, strategies=strategies, budget=arguments.budget
                )
            )
        )
        return 0
    if command == "graph":
        _print_json(
            graph_demo(
                arguments.incident,
                selected_only=arguments.selected_only,
                strategy=arguments.strategy,
                budget=arguments.budget,
            )
        )
        return 0
    if command == "explain":
        _print_json(
            explain_demo(
                arguments.incident,
                arguments.source,
                strategy=arguments.strategy,
                budget=arguments.budget,
            )
        )
        return 0
    _print_json(
        reproduce_demo(arguments.incident, strategy=arguments.strategy, budget=arguments.budget)
    )
    return 0


def _run_ui(arguments: argparse.Namespace) -> int:
    from contextc.observatory import launch_observatory

    return launch_observatory(address=arguments.address, port=arguments.port)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and convert expected failures into concise user errors."""

    parser = build_parser()
    arguments = parser.parse_args(argv)
    try:
        if arguments.command == "version":
            print(__version__)
            return 0
        if arguments.command == "doctor":
            return _run_doctor(arguments)
        if arguments.command == "index":
            return _run_index(arguments)
        if arguments.command == "compile":
            return _run_compile(arguments)
        if arguments.command == "cache":
            return _run_cache(arguments)
        if arguments.command == "mcp":
            return _run_mcp(arguments)
        if arguments.command == "reproduce":
            return _run_reproduce(arguments)
        if arguments.command == "inspect":
            return _run_stored_evidence(arguments, explain=False)
        if arguments.command == "explain":
            return _run_stored_evidence(arguments, explain=True)
        if arguments.command == "benchmark":
            return _run_benchmark(arguments)
        if arguments.command == "case-study":
            return _run_case_study(arguments)
        if arguments.command == "policy":
            return _run_policy(arguments)
        if arguments.command == "security":
            return _run_security(arguments)
        if arguments.command == "demo":
            return _run_demo(arguments)
        if arguments.command == "ui":
            return _run_ui(arguments)
        parser.print_help()
        return 0
    except SecurityPolicyBlockedError as error:
        print(f"contextc: error: {error}", file=sys.stderr)
        return 3
    except (ContextCompilerError, OSError, ValueError) as error:
        print(f"contextc: error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
