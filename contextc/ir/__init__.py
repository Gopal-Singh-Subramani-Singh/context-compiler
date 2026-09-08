"""Typed Context Compiler intermediate representation."""

from contextc.ir.analysis import NodeAnalysis
from contextc.ir.compilation import (
    CompilationUnit,
    CompiledContext,
    SelectionResult,
    SelectionStatus,
)
from contextc.ir.edges import ContextEdge, EdgeType
from contextc.ir.graph import ContextGraph, DependencyClosure
from contextc.ir.nodes import ContextNode, NodeKind
from contextc.ir.selection import DeterministicBaselineSelection, SelectionStrategy
from contextc.ir.source import InstructionAuthority, Sensitivity, SourceReference, TrustDomain
from contextc.optimization.models import ObjectiveWeights, OptimizerConfiguration, OptimizerLimits

__all__ = [
    "CompilationUnit",
    "CompiledContext",
    "ContextEdge",
    "ContextGraph",
    "ContextNode",
    "DependencyClosure",
    "DeterministicBaselineSelection",
    "EdgeType",
    "InstructionAuthority",
    "NodeAnalysis",
    "NodeKind",
    "ObjectiveWeights",
    "OptimizerConfiguration",
    "OptimizerLimits",
    "SelectionResult",
    "SelectionStatus",
    "SelectionStrategy",
    "Sensitivity",
    "SourceReference",
    "TrustDomain",
]
