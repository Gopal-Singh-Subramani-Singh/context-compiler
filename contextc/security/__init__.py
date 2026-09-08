"""M9 structural security analysis."""

from contextc.security.analysis import ANALYSIS_VERSION, analyze_security
from contextc.security.apply import apply_security_result
from contextc.security.models import (
    PolicyAction,
    SecurityDecision,
    SecurityPolicy,
    SecurityResult,
    SecurityRule,
    TaintLimits,
    TaintPath,
)
from contextc.security.policy import load_policy, policy_from_mapping, policy_identity
from contextc.security.service import SecurityService

__all__ = [
    "ANALYSIS_VERSION",
    "PolicyAction",
    "SecurityDecision",
    "SecurityPolicy",
    "SecurityResult",
    "SecurityRule",
    "SecurityService",
    "TaintLimits",
    "TaintPath",
    "analyze_security",
    "apply_security_result",
    "load_policy",
    "policy_from_mapping",
    "policy_identity",
]
