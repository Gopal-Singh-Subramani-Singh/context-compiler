"""M5 optimizer correctness API."""

from typing import TYPE_CHECKING, Any

from contextc.optimization.models import (
    OPTIMIZER_IDS,
    REQUESTED_OPTIMIZER_IDS,
    ObjectiveWeights,
    OptimizerConfiguration,
    OptimizerLimits,
)

if TYPE_CHECKING:
    from contextc.optimization.cascade import (
        DeterministicOptimizerCascade,
        OptimizerDecision,
        choose_optimizer,
    )
    from contextc.optimization.problem import ConstraintViolation, SelectionProblem
    from contextc.optimization.strategies import (
        BruteForceSelection,
        DensityGreedySelection,
        DynamicProgrammingSelection,
        GraphClosureGreedySelection,
        ILPSelection,
        NaiveSelection,
        RecencySelection,
        RelevanceGreedySelection,
        TopKSelection,
        strategy_for,
    )

_CASCADE_EXPORTS = {
    "DeterministicOptimizerCascade",
    "OptimizerDecision",
    "choose_optimizer",
}
_PROBLEM_EXPORTS = {"ConstraintViolation", "SelectionProblem"}
_STRATEGY_EXPORTS = {
    "BruteForceSelection",
    "DensityGreedySelection",
    "DynamicProgrammingSelection",
    "GraphClosureGreedySelection",
    "ILPSelection",
    "NaiveSelection",
    "RecencySelection",
    "RelevanceGreedySelection",
    "TopKSelection",
    "strategy_for",
}


def __getattr__(name: str) -> Any:
    """Load implementations lazily so compilation models remain acyclic."""

    if name in _CASCADE_EXPORTS:
        from contextc.optimization import cascade

        return getattr(cascade, name)
    if name in _PROBLEM_EXPORTS:
        from contextc.optimization import problem

        return getattr(problem, name)
    if name in _STRATEGY_EXPORTS:
        from contextc.optimization import strategies

        return getattr(strategies, name)
    raise AttributeError(name)


__all__ = [
    "OPTIMIZER_IDS",
    "REQUESTED_OPTIMIZER_IDS",
    "BruteForceSelection",
    "ConstraintViolation",
    "DensityGreedySelection",
    "DeterministicOptimizerCascade",
    "DynamicProgrammingSelection",
    "GraphClosureGreedySelection",
    "ILPSelection",
    "NaiveSelection",
    "ObjectiveWeights",
    "OptimizerConfiguration",
    "OptimizerDecision",
    "OptimizerLimits",
    "RecencySelection",
    "RelevanceGreedySelection",
    "SelectionProblem",
    "TopKSelection",
    "choose_optimizer",
    "strategy_for",
]
