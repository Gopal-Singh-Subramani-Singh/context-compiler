"""Stable diagnostic API."""

from contextc.diagnostics.codes import DiagnosticCode
from contextc.diagnostics.models import Diagnostic, DiagnosticDefinition, Severity
from contextc.diagnostics.registry import REGISTRY, get_definition

__all__ = [
    "REGISTRY",
    "Diagnostic",
    "DiagnosticCode",
    "DiagnosticDefinition",
    "Severity",
    "get_definition",
]
