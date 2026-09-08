"""Public-input compilation followed by isolated evaluator-side scoring."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from contextc.application.compile import (
    CompileRepositoryRequest,
    PreparedTargetInputs,
    TargetCompilation,
    compile_prepared_target,
    prepare_repository_index_target,
)
from contextc.optimization.models import OptimizerConfiguration
from contextc.parsers import IndexResult, RepositoryParser
from contextc.targets import TargetId

from .public import PublicBenchmarkTask


@dataclass(frozen=True, slots=True)
class PublicCompilation:
    request: CompileRepositoryRequest
    result: TargetCompilation
    compilation_latency_ms: float


SymbolResolver = Callable[[tuple[str, ...]], tuple[str, ...]]


def _public_index_and_symbols(
    task: PublicBenchmarkTask,
) -> tuple[IndexResult, SymbolResolver]:
    index = RepositoryParser(revision=task.source_revision).parse(task.repository)
    symbols: dict[str, list[str]] = {}
    for node in index.nodes:
        symbol = node.metadata.get("symbol")
        if isinstance(symbol, str):
            symbols.setdefault(symbol, []).append(node.node_id)

    def resolve(names: tuple[str, ...]) -> tuple[str, ...]:
        missing = sorted(set(names) - set(symbols))
        if missing:
            raise ValueError(f"benchmark public task references unknown symbols: {missing}")
        return tuple(sorted(node_id for name in names for node_id in symbols[name]))

    return index, resolve


def _public_request(
    task: PublicBenchmarkTask,
    *,
    strategy: str,
    resolve: SymbolResolver,
) -> CompileRepositoryRequest:
    return CompileRepositoryRequest(
        repository=task.repository,
        task=task.description,
        target_id=TargetId.GENERIC,
        token_budget=task.token_budget,
        time_anchor=task.time_anchor,
        source_revision=task.source_revision,
        system_instruction=task.system_instruction,
        optimizer=OptimizerConfiguration(
            requested_strategy=strategy,
            source_content_allowance=task.source_content_allowance,
            mandatory_node_ids=resolve(task.mandatory_symbols),
            blocked_node_ids=resolve(task.blocked_symbols),
        ),
    )


def compile_public_tasks(
    task: PublicBenchmarkTask, *, strategies: tuple[str, ...]
) -> tuple[PublicCompilation, ...]:
    """Share sealed parse/analysis facts and charge the same setup latency to each strategy."""

    if not strategies:
        raise ValueError("public compilation requires at least one strategy")
    started = time.perf_counter()
    index, resolve = _public_index_and_symbols(task)
    requests = tuple(
        _public_request(task, strategy=strategy, resolve=resolve) for strategy in strategies
    )
    prepared: PreparedTargetInputs = prepare_repository_index_target(requests[0], index)
    setup_latency_ms = (time.perf_counter() - started) * 1000
    compilations = []
    for request in requests:
        strategy_started = time.perf_counter()
        result = compile_prepared_target(request, prepared)
        latency_ms = setup_latency_ms + (time.perf_counter() - strategy_started) * 1000
        compilations.append(
            PublicCompilation(
                request=request,
                result=result,
                compilation_latency_ms=latency_ms,
            )
        )
    return tuple(compilations)


def compile_public_task(task: PublicBenchmarkTask, *, strategy: str) -> PublicCompilation:
    """Compile one public task without accepting or loading evaluator labels."""

    return compile_public_tasks(task, strategies=(strategy,))[0]
