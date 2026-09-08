"""Fully local deterministic M4 reproduction fixture."""

from helper import stable_value


def build_reference_context() -> str:
    return f"reference:{stable_value()}"
